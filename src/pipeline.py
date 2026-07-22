"""Orquestração do pipeline ETL — executa todas as etapas em sequência.

Fluxo: ingestão → deduplicação → padronização → resolução de versões →
validação → KPIs → publicação.

A ordem importa. A deduplicação exata vem antes da padronização porque não
depende das chaves; a validação vem depois da consolidação, para não acusar
como erro uma duplicata que o próprio pipeline resolve na etapa seguinte.

A publicação produz sempre um Parquet tipado (formato principal, consultável
por SQL local) e, opcionalmente, um CSV padronizado para ferramentas de BI.
"""

import json
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pandas as pd

from analytics.kpis import compute_kpis
from audit.auditor import criar_relatorio_pipeline
from consolidation.consolidator import consolidate, resolve_versoes
from export.formatters import export_to_csv, export_to_parquet
from export.schema import VERSAO_SCHEMA, aplicar_schema
from ingestion.directory import ingest_directory
from ingestion.legado import ingest_legado
from transformation.standardizer import standardize
from validation.validator import ValidationReport, validate_and_partition

PARQUET_NOME = "vendas_consolidadas.parquet"
CSV_NOME = "vendas_consolidadas.csv"
AUDITORIA_NOME = "execucao.json"


class PipelineContractError(ValueError):
    """O dataset não tem a estrutura mínima para ser publicado."""


def _novo_run_id() -> str:
    instante = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{instante}-{uuid4().hex[:8]}"


def _versao_pipeline() -> str:
    try:
        return version("projeto-aldebaran")
    except PackageNotFoundError:  # pragma: no cover - execução sem instalação
        return "desconhecida"


def _revisao_codigo() -> str:
    """Identifica o commit e declara quando o código executado está modificado."""
    try:
        revisao = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        sujo = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        return revisao + ("+dirty" if sujo else "")
    except (OSError, subprocess.SubprocessError):
        return "desconhecida"


def _fingerprint(path: Path) -> dict:
    digest = sha256()
    with path.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return {
        "arquivo": path.name,
        "tamanho_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _entradas_auditadas(
    data_dir: str | Path,
    legado_dir: str | Path | None,
) -> list[dict]:
    arquivos: list[tuple[str, Path]] = []
    atual = Path(data_dir)
    if atual.is_dir():
        arquivos.extend(
            ("ATUAL", path)
            for path in atual.iterdir()
            if path.is_file() and path.suffix.lower() in {".xlsx", ".xls"}
        )
    if legado_dir is not None:
        legado = Path(legado_dir)
        if legado.is_dir():
            arquivos.extend(
                ("LEGADO", path)
                for path in legado.iterdir()
                if path.is_file() and path.suffix.lower() == ".rel"
            )
    return [
        {"sistema_origem": sistema, **_fingerprint(path)}
        for sistema, path in sorted(arquivos, key=lambda item: (item[0], item[1].name))
    ]


def _promover_com_rollback(
    artefatos: list[tuple[Path, Path]],
    run_id: str,
) -> None:
    """Promove um conjunto de arquivos e restaura o estado anterior em erro."""
    backups: dict[Path, Path | None] = {}
    promovidos: list[Path] = []
    try:
        for origem, destino in artefatos:
            destino.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if destino.exists():
                backup = destino.with_name(f".{destino.name}.{run_id}.rollback")
                destino.replace(backup)
            backups[destino] = backup
            try:
                origem.replace(destino)
            except Exception:
                if backup is not None and backup.exists():
                    backup.replace(destino)
                backups[destino] = None
                raise
            promovidos.append(destino)
    except Exception:
        for destino in reversed(promovidos):
            if destino.exists():
                destino.unlink()
            backup = backups.get(destino)
            if backup is not None and backup.exists():
                backup.replace(destino)
        raise
    else:
        for backup in backups.values():
            if backup is not None and backup.exists():
                backup.unlink()


def run_pipeline(
    data_dir: str | Path = "data/raw",
    output_dir: str | Path = "data/processed",
    csv_path: str | Path | None = None,
    exportar_csv: bool = False,
    legado_dir: str | Path | None = "data/legado",
    quarantine_dir: str | Path | None = None,
) -> dict:
    """Executa o pipeline e preserva auditoria também em falhas fatais."""
    run_id = _novo_run_id()
    etapas: dict[str, dict] = {}
    entradas: list[dict] = []
    try:
        entradas = _entradas_auditadas(data_dir, legado_dir)
        return _run_pipeline(
            data_dir=data_dir,
            output_dir=output_dir,
            csv_path=csv_path,
            exportar_csv=exportar_csv,
            legado_dir=legado_dir,
            quarantine_dir=quarantine_dir,
            run_id=run_id,
            etapas=etapas,
            entradas_auditadas=entradas,
        )
    except Exception as exc:
        auditoria = criar_relatorio_pipeline(
            etapas,
            id_execucao=run_id,
            versao_pipeline=_versao_pipeline(),
            versao_schema=VERSAO_SCHEMA,
            revisao_codigo=_revisao_codigo(),
            status="FALHA",
            entradas=entradas,
        )
        auditoria.erros = [f"{type(exc).__name__}: {exc}"]
        falha = Path(output_dir) / "auditoria" / f"{run_id}-falha.json"
        try:
            relatorio = ValidationReport(total_rows=0, errors=auditoria.erros)
            _gravar_auditoria(auditoria, relatorio, falha, falha)
        except OSError:
            pass
        raise


def _run_pipeline(
    data_dir: str | Path = "data/raw",
    output_dir: str | Path = "data/processed",
    csv_path: str | Path | None = None,
    exportar_csv: bool = False,
    legado_dir: str | Path | None = "data/legado",
    quarantine_dir: str | Path | None = None,
    *,
    run_id: str,
    etapas: dict[str, dict],
    entradas_auditadas: list[dict],
) -> dict:
    """Executa o pipeline completo, unindo o ERP atual e o legado.

    Args:
        data_dir: Diretório com os arquivos .xlsx/.xls do ERP atual.
        output_dir: Diretório de publicação (Parquet e auditoria).
        csv_path: Caminho do CSV. Se None, usa `data/exports/<CSV_NOME>`.
        exportar_csv: Gera também o CSV padronizado para BI.
        legado_dir: Diretório com os `.rel` do ERP legado. Se None ou
            inexistente, publica apenas o histórico do sistema atual.

    Returns:
        Dict com `dados` (DataFrame publicado), `kpis`, `validacao`
        (ValidationReport), `etapas`, `auditoria` (PipelineRun) e `legado`
        (arquivos ingeridos e ignorados, com o motivo).
    """
    t0 = time.time()
    df_atual = ingest_directory(data_dir)
    etapas["ingestao"] = {
        "linhas": len(df_atual),
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    if legado_dir:
        df_legado, rel_legado = ingest_legado(legado_dir)
    else:
        df_legado, rel_legado = pd.DataFrame(), {"ingeridos": [], "ignorados": [], "linhas": 0}
    etapas["ingestao_legado"] = {
        "linhas": len(df_legado),
        "arquivos": len(rel_legado["ingeridos"]),
        "ignorados": len(rel_legado["ignorados"]),
        "duracao_s": round(time.time() - t0, 2),
    }

    quadros = [q for q in (df_atual, df_legado) if not q.empty]
    df = pd.concat(quadros, ignore_index=True) if quadros else pd.DataFrame()
    if df.empty:
        raise PipelineContractError(
            "Nenhum registro de venda foi encontrado nas fontes informadas"
        )

    t0 = time.time()
    df, rel_consolidacao = consolidate(df)
    etapas["deduplicacao"] = {
        "linhas": len(df),
        "removidas": rel_consolidacao["linhas_removidas"],
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    df = standardize(df)
    df["id_execucao"] = run_id
    colisoes = df.attrs.get("colisoes_chave", 0)
    etapas["padronizacao"] = {
        "linhas": len(df),
        "colisoes_chave": colisoes,
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    df, rejeitados_elegibilidade, relatorio_elegibilidade = validate_and_partition(
        df,
        check_uniqueness=False,
    )
    if relatorio_elegibilidade.has_structural_errors:
        raise PipelineContractError(
            "; ".join(relatorio_elegibilidade.structural_errors)
        )
    etapas["elegibilidade"] = {
        "linhas": len(df),
        "rejeitadas": len(rejeitados_elegibilidade),
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    df, rel_versoes = resolve_versoes(df)
    etapas["versoes"] = {
        "linhas": len(df),
        "substituidas": rel_versoes["versoes_substituidas"],
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    df, rejeitados_finais, relatorio_validacao = validate_and_partition(df)
    if relatorio_validacao.has_structural_errors:
        raise PipelineContractError("; ".join(relatorio_validacao.structural_errors))

    rejeitados_validacao = pd.concat(
        [
            quadro
            for quadro in (rejeitados_elegibilidade, rejeitados_finais)
            if not quadro.empty
        ],
        ignore_index=True,
    ) if (not rejeitados_elegibilidade.empty or not rejeitados_finais.empty) else pd.DataFrame()
    relatorio_validacao.total_rows = relatorio_elegibilidade.total_rows
    relatorio_validacao.rejected_rows = len(rejeitados_validacao)
    relatorio_validacao.errors = (
        [f"{len(rejeitados_validacao)} registro(s) rejeitado(s)"]
        if len(rejeitados_validacao)
        else []
    )

    conflitos = pd.DataFrame(rel_versoes.get("conflitos", []))
    if not conflitos.empty:
        conflitos["codigo_rejeicao"] = "CONFLITO_VERSAO"
        conflitos["motivo_rejeicao"] = (
            "Versões diferentes têm o mesmo período; nenhuma foi escolhida automaticamente"
        )
    rejeitados = pd.concat(
        [quadro for quadro in (rejeitados_validacao, conflitos) if not quadro.empty],
        ignore_index=True,
    ) if (not rejeitados_validacao.empty or not conflitos.empty) else pd.DataFrame()
    if colisoes:
        relatorio_validacao.warnings.append(
            f"{colisoes} colisao(oes) de chave desambiguada(s) por falta de data"
        )
    etapas["validacao"] = {
        "linhas": len(df),
        "erros": relatorio_validacao.total_errors(),
        "avisos": len(relatorio_validacao.warnings),
        "rejeitadas": len(rejeitados),
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    kpis = compute_kpis(df)
    etapas["analytics"] = {"duracao_s": round(time.time() - t0, 2)}
    dados_publicados = aplicar_schema(df)

    # --- Publicação ---
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    parquet_destino = (output_path / PARQUET_NOME).resolve()
    csv_destino = (
        (Path(csv_path) if csv_path else Path("data/exports") / CSV_NOME).resolve()
        if exportar_csv
        else None
    )
    quarentena_destino = None
    if not rejeitados.empty:
        raiz_quarentena = (
            Path(quarantine_dir)
            if quarantine_dir is not None
            else output_path.parent / "quarantine"
        )
        quarentena_destino = (
            raiz_quarentena / run_id / "registros_rejeitados.parquet"
        ).resolve()

    auditoria_destino = (output_path / AUDITORIA_NOME).resolve()
    historico_destino = (output_path / "auditoria" / f"{run_id}.json").resolve()

    # Prepara todos os artefatos antes de substituir a publicação corrente.
    # `execucao.json` é o marcador final de uma execução concluída.
    with TemporaryDirectory(prefix=".aldebaran-", dir=output_path) as staging_dir:
        staging = Path(staging_dir)

        t0 = time.time()
        parquet_staging = export_to_parquet(dados_publicados, staging / PARQUET_NOME)
        etapas["parquet"] = {
            "destino": str(parquet_destino),
            "linhas": len(df),
            "tamanho_mb": round(parquet_staging.stat().st_size / 1024 / 1024, 2),
            "duracao_s": round(time.time() - t0, 2),
        }

        csv_staging = None
        if csv_destino is not None:
            t0 = time.time()
            csv_staging = export_to_csv(
                dados_publicados,
                staging / "csv" / csv_destino.name,
            )
            etapas["csv"] = {
                "destino": str(csv_destino),
                "linhas": len(df),
                "tamanho_mb": round(csv_staging.stat().st_size / 1024 / 1024, 2),
                "duracao_s": round(time.time() - t0, 2),
            }

        quarentena_staging = None
        if quarentena_destino is not None:
            quarentena_staging = staging / "quarantine" / quarentena_destino.name
            quarentena_staging.parent.mkdir(parents=True, exist_ok=True)
            rejeitados = rejeitados.copy()
            rejeitados["id_execucao"] = run_id
            rejeitados["registro_original_json"] = rejeitados.apply(
                lambda linha: json.dumps(linha.to_dict(), ensure_ascii=False, default=str),
                axis=1,
            )
            rejeitados.to_parquet(quarentena_staging, index=False)
            etapas["quarentena"] = {
                "destino": str(quarentena_destino),
                "linhas": len(rejeitados),
                "duracao_s": 0.0,
            }

        saidas_auditadas = [
            {**_fingerprint(parquet_staging), "destino": str(parquet_destino)}
        ]
        if csv_staging is not None:
            saidas_auditadas.append(
                {**_fingerprint(csv_staging), "destino": str(csv_destino)}
            )
        if quarentena_staging is not None:
            saidas_auditadas.append(
                {
                    **_fingerprint(quarentena_staging),
                    "destino": str(quarentena_destino),
                }
            )
        status_execucao = "PARCIAL" if len(rejeitados) else "SUCESSO"
        auditoria = criar_relatorio_pipeline(
            etapas,
            id_execucao=run_id,
            versao_pipeline=_versao_pipeline(),
            versao_schema=VERSAO_SCHEMA,
            revisao_codigo=_revisao_codigo(),
            status=status_execucao,
            entradas=entradas_auditadas,
            saidas=saidas_auditadas,
        )
        auditoria.erros = list(relatorio_validacao.errors)
        auditoria_staging = staging / AUDITORIA_NOME
        historico_staging = staging / "auditoria" / f"{run_id}.json"
        _gravar_auditoria(
            auditoria,
            relatorio_validacao,
            auditoria_staging,
            historico_staging,
        )

        artefatos: list[tuple[Path, Path]] = []
        if quarentena_staging is not None and quarentena_destino is not None:
            artefatos.append((quarentena_staging, quarentena_destino))
        if csv_staging is not None and csv_destino is not None:
            artefatos.append((csv_staging, csv_destino))
        artefatos.extend([
            (historico_staging, historico_destino),
            (parquet_staging, parquet_destino),
            (auditoria_staging, auditoria_destino),
        ])
        _promover_com_rollback(artefatos, run_id)

    return {
        "dados": dados_publicados,
        "kpis": kpis,
        "validacao": relatorio_validacao,
        "etapas": etapas,
        "auditoria": auditoria,
        "legado": rel_legado,
        "run_id": run_id,
        "status": status_execucao,
        "quarentena": quarentena_destino,
    }


def _gravar_auditoria(
    auditoria,
    relatorio_validacao,
    path: Path,
    historico_path: Path,
) -> Path:
    """Persiste o registro da execução, para que qualquer número publicado
    possa ser reconduzido à execução que o produziu."""
    conteudo = asdict(auditoria)
    conteudo["validacao"] = {
        "linhas": relatorio_validacao.total_rows,
        "erros": relatorio_validacao.errors,
        "avisos": relatorio_validacao.warnings,
    }
    serializado = json.dumps(conteudo, indent=2, ensure_ascii=False)
    historico_path.parent.mkdir(parents=True, exist_ok=True)
    historico_path.write_text(serializado, encoding="utf-8")
    path.write_text(serializado, encoding="utf-8")
    return path

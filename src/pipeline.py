"""Orquestração do pipeline ETL — executa todas as etapas em sequência."""

from pathlib import Path
from typing import Union

from ingestion.directory import ingest_directory
from transformation.standardizer import standardize
from consolidation.consolidator import consolidate
from analytics.kpis import compute_kpis
from export.formatters import export_to_csv_looker


def run_pipeline(
    data_dir: Union[str, Path] = "data/raw",
    output_dir: Union[str, Path] = "data/processed",
    csv_path: Union[str, Path, None] = None,
) -> dict:
    """Executa o pipeline completo: ingestão → padronização → consolidação → KPIs.

    Gera automaticamente:
      - <output_dir>/vendas_consolidadas.parquet (dados tratados)
      - <csv_path> (Power BI ready, default: data/exports/vendas_consolidadas.csv)

    Args:
        data_dir: Diretório com os ficheiros .xlsx/.xls de origem.
        output_dir: Diretório onde salvar os dados processados (Parquet).
        csv_path: Caminho do CSV de saída. Se None, usa data/exports/vendas_consolidadas.csv.

    Returns:
        Dict com:
          - dados: DataFrame padronizado e consolidado
          - kpis: Métricas calculadas
          - etapas: Relatório de cada etapa (linhas, duração)
    """
    import time

    etapas = {}

    t0 = time.time()
    df = ingest_directory(data_dir)
    etapas["ingestao"] = {"linhas": len(df), "duracao_s": round(time.time() - t0, 2)}

    t0 = time.time()
    df = standardize(df)
    etapas["padronizacao"] = {"linhas": len(df), "duracao_s": round(time.time() - t0, 2)}

    t0 = time.time()
    df, rel_consolidacao = consolidate(df)
    etapas["consolidacao"] = {
        "linhas": len(df),
        "removidas": rel_consolidacao["linhas_removidas"],
        "duracao_s": round(time.time() - t0, 2),
    }

    t0 = time.time()
    kpis = compute_kpis(df)
    etapas["analytics"] = {"duracao_s": round(time.time() - t0, 2)}

    # --- Persistência automática ---
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Parquet (para reprocessamento)
    df.to_parquet(output_path / "vendas_consolidadas.parquet", index=False)
    etapas["parquet"] = {
        "destino": str((output_path / "vendas_consolidadas.parquet").resolve()),
        "tamanho_mb": round(
            (output_path / "vendas_consolidadas.parquet").stat().st_size / 1024 / 1024, 1
        ),
        "duracao_s": round(time.time() - t0, 2),
    }

    # CSV Power BI
    if csv_path is None:
        csv_path = Path("data/exports") / "vendas_consolidadas.csv"
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    export_to_csv_looker(df, csv_path)
    etapas["csv"] = {
        "destino": str(csv_path.resolve()),
        "tamanho_mb": round(csv_path.stat().st_size / 1024 / 1024, 1),
        "linhas": len(df),
        "formato": "Looker Studio (, UTF-8 AAAA-MM-DD)",
    }

    return {
        "dados": df,
        "kpis": kpis,
        "etapas": etapas,
    }

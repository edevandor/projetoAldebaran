"""Auditoria de execução do pipeline — rastreabilidade e estatísticas."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class PipelineRun:
    """Registo de uma execução do pipeline.

    Attributes:
        timestamp: ISO timestamp do início da execução.
        duracao_s: Duração total em segundos.
        etapas: Dict com nome da etapa → métricas.
        erros: Lista de mensagens de erro (vazia se bem-sucedido).
    """
    id_execucao: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    versao_pipeline: str = ""
    versao_schema: str = ""
    revisao_codigo: str = ""
    status: str = "SUCESSO"
    entradas: list[dict[str, Any]] = field(default_factory=list)
    saidas: list[dict[str, Any]] = field(default_factory=list)
    duracao_s: float = 0.0
    etapas: dict[str, Any] = field(default_factory=dict)
    erros: list[str] = field(default_factory=list)

    @property
    def sucesso(self) -> bool:
        return self.status == "SUCESSO" and not self.erros

    def linhas_publicadas(self) -> int:
        """Linhas que chegaram ao fim do pipeline.

        É a contagem da última etapa que reportou linhas — somar todas as
        etapas contaria o mesmo dado uma vez por etapa.
        """
        parquet = self.etapas.get("parquet", {})
        if isinstance(parquet, dict) and "linhas" in parquet:
            return parquet["linhas"]
        contagens = [
            etapa["linhas"]
            for etapa in self.etapas.values()
            if isinstance(etapa, dict) and "linhas" in etapa
        ]
        return contagens[-1] if contagens else 0

    def resumo(self) -> str:
        """Resumo de uma linha da execução."""
        status_resumo = "FALHA" if self.status == "SUCESSO" and self.erros else self.status
        simbolo = {"SUCESSO": "✓", "PARCIAL": "!", "FALHA": "✗"}.get(
            status_resumo,
            "?",
        )
        linhas = f"{self.linhas_publicadas():,}".replace(",", ".")
        return (
            f"[{self.timestamp}] {simbolo} "
            f"{len(self.etapas)} etapas, "
            f"{linhas} linhas, "
            f"{self.duracao_s:.1f}s"
            + (f" | {len(self.erros)} erro(s)" if not self.sucesso else "")
        )


def criar_relatorio_pipeline(
    etapas: dict[str, Any],
    *,
    id_execucao: str = "",
    versao_pipeline: str = "",
    versao_schema: str = "",
    revisao_codigo: str = "",
    status: str = "SUCESSO",
    entradas: list[dict[str, Any]] | None = None,
    saidas: list[dict[str, Any]] | None = None,
) -> PipelineRun:
    """Cria um relatório de auditoria a partir das etapas executadas.

    Args:
        etapas: Dict com nome da etapa → métricas (formato de run_pipeline).

    Returns:
        PipelineRun com o registro da execução.
    """
    duracao_total = sum(
        e.get("duracao_s", 0) for e in etapas.values() if isinstance(e, dict)
    )
    return PipelineRun(
        id_execucao=id_execucao,
        versao_pipeline=versao_pipeline,
        versao_schema=versao_schema,
        revisao_codigo=revisao_codigo,
        status=status,
        entradas=entradas or [],
        saidas=saidas or [],
        duracao_s=round(duracao_total, 2),
        etapas=etapas,
    )

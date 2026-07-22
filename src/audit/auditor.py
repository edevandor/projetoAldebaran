"""Auditoria de execução do pipeline — rastreabilidade e estatísticas."""

import time
from dataclasses import dataclass, field
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
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    duracao_s: float = 0.0
    etapas: dict[str, Any] = field(default_factory=dict)
    erros: list[str] = field(default_factory=list)

    @property
    def sucesso(self) -> bool:
        return len(self.erros) == 0

    def resumo(self) -> str:
        """Resumo de uma linha da execução."""
        status = "✓" if self.sucesso else "✗"
        linhas_total = sum(
            e.get("linhas", 0) for e in self.etapas.values()
            if isinstance(e, dict)
        )
        return (
            f"[{self.timestamp}] {status} "
            f"{len(self.etapas)} etapas, "
            f"{linhas_total:,} linhas, "
            f"{self.duracao_s:.1f}s"
            + (f" | {len(self.erros)} erro(s)" if not self.sucesso else "")
        )


def criar_relatorio_pipeline(etapas: dict[str, Any]) -> PipelineRun:
    """Cria um relatório de auditoria a partir das etapas executadas.

    Args:
        etapas: Dict com nome da etapa → métricas (formato de run_pipeline).

    Returns:
        PipelineRun com o registo da execução.
    """
    duracao_total = sum(
        e.get("duracao_s", 0) for e in etapas.values() if isinstance(e, dict)
    )
    return PipelineRun(
        duracao_s=round(duracao_total, 2),
        etapas=etapas,
    )

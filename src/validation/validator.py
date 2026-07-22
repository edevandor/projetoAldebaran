"""Validação de dados padronizados de vendas."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationReport:
    """Relatório de validação."""

    total_rows: int
    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Indica se o relatório contém erros."""
        return bool(self.errors)

    def total_errors(self) -> int:
        """Retorna a quantidade total de erros."""
        return len(self.errors)

    def summary(self) -> str:
        """Retorna um resumo legível da validação."""
        if not self.errors:
            return f"OK - {self.total_rows} linhas, 0 erros"
        details = "; ".join(self.errors)
        return f"{self.total_errors()} erro(s) em {self.total_rows} linhas: {details}"


def validate(df: pd.DataFrame) -> ValidationReport:
    """Valida um DataFrame padronizado."""
    errors: list[str] = []
    required_fields = ["produto", "data_emissao", "numero_documento", "valor_total_venda"]

    for field_name in required_fields:
        if field_name not in df.columns:
            errors.append(f"Campo obrigatório ausente: {field_name}")
            continue

        column = df[field_name]
        if column.apply(lambda value: pd.isna(value) or str(value).strip() == "").any():
            errors.append(f"Campo obrigatório vazio: {field_name}")

    if "id_venda" in df.columns and df["id_venda"].duplicated(keep=False).any():
        errors.append("Duplicatas encontradas em id_venda")

    return ValidationReport(total_rows=len(df), errors=errors)

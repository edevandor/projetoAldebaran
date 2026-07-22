"""Validação de dados padronizados de vendas."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from export.schema import CONTRATO_SAIDA

CAMPOS_OBRIGATORIOS = (
    "produto",
    "numero_documento",
    "valor_total_venda",
)


@dataclass
class ValidationReport:
    """Relatório de validação.

    `errors` quebram o contrato do dataset. `warnings` registram lacunas
    conhecidas da origem que não invalidam a linha — o registro continua
    no dataset, sinalizado.
    """

    total_rows: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_rows: int = 0
    structural_errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Indica se o relatório contém erros."""
        return bool(self.errors)

    @property
    def has_structural_errors(self) -> bool:
        return bool(self.structural_errors)

    def total_errors(self) -> int:
        """Retorna a quantidade total de erros."""
        return len(self.errors)

    def summary(self) -> str:
        """Retorna um resumo legível da validação."""
        if not self.errors:
            base = f"OK - {self.total_rows} linhas, 0 erros"
        else:
            details = "; ".join(self.errors)
            base = f"{self.total_errors()} erro(s) em {self.total_rows} linhas: {details}"
        if self.warnings:
            base += f" | {len(self.warnings)} aviso(s): " + "; ".join(self.warnings)
        return base


def validate(df: pd.DataFrame) -> ValidationReport:
    """Valida um DataFrame padronizado contra as regras de negócio.

    Regras aplicadas:
      - campos obrigatórios presentes e preenchidos;
      - `id_item_venda` único — é a chave primária do dataset.

    `id_venda` **não** é validado como único: a granularidade é o item,
    e uma nota fiscal com vários itens produz várias linhas com o mesmo
    `id_venda` (ver DECISIONS.md, D-009).

    Datas ausentes entram como aviso, não erro: a migração de servidor
    de 2023 deixou registros sem datação e descartá-los perderia venda real.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for field_name in CAMPOS_OBRIGATORIOS:
        if field_name not in df.columns:
            errors.append(f"Campo obrigatório ausente: {field_name}")
            continue

        column = df[field_name]
        if column.apply(lambda value: pd.isna(value) or str(value).strip() == "").any():
            errors.append(f"Campo obrigatório vazio: {field_name}")

    if "id_item_venda" in df.columns:
        duplicadas = int(df["id_item_venda"].duplicated(keep=False).sum())
        if duplicadas:
            errors.append(
                f"Duplicatas encontradas em id_item_venda: {duplicadas} linha(s)"
            )
    else:
        errors.append("Campo obrigatório ausente: id_item_venda")

    if "data_emissao" in df.columns:
        sem_data = int(df["data_emissao"].isna().sum())
        if sem_data:
            warnings.append(f"{sem_data} linha(s) sem data_emissao")
    else:
        errors.append("Campo obrigatório ausente: data_emissao")

    return ValidationReport(total_rows=len(df), errors=errors, warnings=warnings)


def validate_and_partition(
    df: pd.DataFrame,
    *,
    check_uniqueness: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, ValidationReport]:
    """Separa registros válidos dos que violam o contrato de saída.

    A unicidade pode ser adiada enquanto versões legítimas da mesma identidade
    ainda precisam ser resolvidas pela consolidação.
    """
    obrigatorios = [
        coluna for coluna, especificacao in CONTRATO_SAIDA.items() if not especificacao.nullable
    ]
    ausentes = [coluna for coluna in obrigatorios if coluna not in df.columns]
    if ausentes:
        erros = [f"Campo obrigatório ausente: {coluna}" for coluna in ausentes]
        return (
            df.iloc[0:0].copy(),
            df.iloc[0:0].copy(),
            ValidationReport(total_rows=len(df), errors=erros, structural_errors=erros),
        )

    motivos: dict[int, list[str]] = {}
    codigos: dict[int, set[str]] = {}
    for coluna in obrigatorios:
        vazios = df[coluna].apply(lambda valor: pd.isna(valor) or str(valor).strip() == "")
        for indice in df.index[vazios]:
            motivos.setdefault(int(indice), []).append(coluna)
            codigos.setdefault(int(indice), set()).add("CAMPO_OBRIGATORIO_VAZIO")

    # Uma linha já inválida não deve contaminar outra linha válida apenas
    # porque carrega uma chave derivada inconsistente. A unicidade é avaliada
    # entre os candidatos que ainda podem ser publicados.
    if check_uniqueness:
        indices_candidatos = df.index.difference(list(motivos))
        duplicadas = df.loc[indices_candidatos, "id_item_venda"].duplicated(keep=False)
        for indice in duplicadas.index[duplicadas]:
            motivos.setdefault(int(indice), []).append("id_item_venda duplicado")
            codigos.setdefault(int(indice), set()).add("CHAVE_DUPLICADA")

    rejeitados = df.loc[list(motivos)].copy() if motivos else df.iloc[0:0].copy()
    if not rejeitados.empty:
        rejeitados["codigo_rejeicao"] = [
            ",".join(sorted(codigos[int(indice)])) for indice in rejeitados.index
        ]
        rejeitados["motivo_rejeicao"] = [
            "Violação(ões) do contrato: " + ", ".join(motivos[int(indice)])
            for indice in rejeitados.index
        ]

    aceitos = df.drop(index=list(motivos)).reset_index(drop=True)
    rejeitados = rejeitados.reset_index(drop=True)
    warnings: list[str] = []
    if "data_emissao" in aceitos.columns:
        sem_data = int(aceitos["data_emissao"].isna().sum())
        if sem_data:
            warnings.append(f"{sem_data} linha(s) sem data_emissao")
    relatorio = ValidationReport(
        total_rows=len(df),
        errors=[f"{len(rejeitados)} registro(s) rejeitado(s)"] if len(rejeitados) else [],
        warnings=warnings,
        rejected_rows=len(rejeitados),
    )
    return aceitos, rejeitados, relatorio

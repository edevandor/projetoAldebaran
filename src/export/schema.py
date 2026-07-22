"""Schema canónico da camada de saída.

Define as colunas, a ordem e os tipos do dataset publicado.
Uma única definição serve tanto ao Parquet (consumo SQL local) como ao
CSV (consumo por ferramentas de BI), garantindo que ambos descrevem
exactamente o mesmo contrato.
"""

from dataclasses import dataclass

import pandas as pd

VERSAO_SCHEMA = "1.2.0"


@dataclass(frozen=True)
class ColumnSpec:
    """Tipo físico e nulabilidade de uma coluna publicada."""

    dtype: str
    nullable: bool

# Coluna → tipo do dataset publicado, na ordem de publicação.
# `datetime64[ns]` é o tipo temporal nativo do Parquet: permite filtro
# e agregação por data em SQL sem CAST.
CONTRATO_SAIDA: dict[str, ColumnSpec] = {
    "id_execucao": ColumnSpec("string", False),
    "id_item_venda": ColumnSpec("string", False),
    "id_venda": ColumnSpec("string", False),
    "data_emissao": ColumnSpec("datetime64[ns]", True),
    "tipo_documento": ColumnSpec("string", False),
    "numero_documento": ColumnSpec("string", False),
    "protocolo": ColumnSpec("string", True),
    "codigo_produto": ColumnSpec("string", True),
    "descricao_produto": ColumnSpec("string", False),
    "quantidade": ColumnSpec("float64", True),
    "unidade_medida": ColumnSpec("string", True),
    "valor_total_venda_centavos": ColumnSpec("int64", False),
    "responsavel": ColumnSpec("string", True),
    "artigo": ColumnSpec("string", True),
    "arquivo_origem": ColumnSpec("string", False),
    "sistema_origem": ColumnSpec("string", False),
    "confianca_data": ColumnSpec("string", False),
    "confianca_identidade": ColumnSpec("string", False),
}

SCHEMA_SAIDA: dict[str, str] = {
    coluna: especificacao.dtype for coluna, especificacao in CONTRATO_SAIDA.items()
}

# Colunas intermediárias descartadas na publicação.
# `produto` é a concatenação de `codigo_produto` + ' - ' + `descricao_produto`,
# ambos já publicados: manter as três seria redundância pura (D-008).
COLUNAS_DESCARTADAS: tuple[str, ...] = ("produto",)


def aplicar_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Devolve o DataFrame reduzido, ordenado e tipado segundo `SCHEMA_SAIDA`.

    Colunas ausentes na entrada são criadas vazias, para que o contrato de
    saída seja estável mesmo quando a origem não traz todos os campos.
    Colunas extra que não constam do schema são descartadas.
    """
    obrigatorias = [
        coluna for coluna, especificacao in CONTRATO_SAIDA.items() if not especificacao.nullable
    ]
    ausentes = [coluna for coluna in obrigatorias if coluna not in df.columns]
    if ausentes and not df.empty:
        raise ValueError(
            "Coluna(s) obrigatória(s) ausente(s): " + ", ".join(ausentes)
        )

    resultado = pd.DataFrame(index=df.index)

    for coluna, tipo in SCHEMA_SAIDA.items():
        if coluna in df.columns:
            serie = df[coluna]
        else:
            serie = pd.Series([pd.NA] * len(df), index=df.index)

        if tipo == "datetime64[ns]":
            resultado[coluna] = pd.to_datetime(serie, errors="coerce").astype(
                "datetime64[ns]"
            )
        elif tipo == "int64":
            numerica = pd.Series(pd.to_numeric(serie, errors="coerce"), index=df.index)
            resultado[coluna] = numerica.astype("Int64")
        elif tipo == "float64":
            resultado[coluna] = pd.to_numeric(serie, errors="coerce").astype("float64")
        else:
            resultado[coluna] = serie.astype("string")

    invalidas = [
        coluna
        for coluna in obrigatorias
        if resultado[coluna].isna().any()
        or (
            pd.api.types.is_string_dtype(resultado[coluna])
            and resultado[coluna].str.strip().eq("").any()
        )
    ]
    if invalidas:
        raise ValueError(
            "Valor inválido em coluna(s) obrigatória(s): " + ", ".join(invalidas)
        )

    return resultado

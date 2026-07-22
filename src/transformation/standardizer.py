"""Padronização de dados de vendas."""

import pandas as pd


def _split_produto(produto: object) -> tuple[str, str]:
    texto = "" if pd.isna(produto) else str(produto)
    if " - " not in texto:
        return "", texto
    codigo, descricao = texto.split(" - ", 1)
    return codigo, descricao


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna uma cópia padronizada do DataFrame."""
    resultado = df.copy()
    split = resultado["produto"].apply(_split_produto)
    resultado["codigo_produto"] = split.str[0]
    resultado["descricao_produto"] = split.str[1]
    resultado["id_venda"] = (
        resultado["tipo_documento"]
        + resultado["numero_documento"]
        + resultado["data_emissao"].astype(str)
    )
    resultado["id_item_venda"] = resultado["id_venda"] + resultado["protocolo"]
    return resultado

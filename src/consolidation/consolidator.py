"""Consolidação dos dados — remoção de duplicatas exatas."""

import pandas as pd


def consolidate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove linhas duplicadas (todas as colunas iguais, exceto arquivo_origem).

    Mantém a primeira ocorrência. Retorna o DataFrame limpo e um relatório.

    Args:
        df: DataFrame padronizado (com codigo_produto, id_venda, etc.).

    Returns:
        Tupla (df_sem_duplicatas, relatorio) onde relatorio é um dict
        com total_original, total_final e linhas_removidas.
    """
    cols_dedup = [c for c in df.columns if c != "arquivo_origem"]
    total_original = len(df)

    df_clean = df.drop_duplicates(subset=cols_dedup, keep="first")
    df_clean = df_clean.reset_index(drop=True)

    total_final = len(df_clean)
    relatorio = {
        "total_original": total_original,
        "total_final": total_final,
        "linhas_removidas": total_original - total_final,
    }
    return df_clean, relatorio

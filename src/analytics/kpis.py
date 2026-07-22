"""Cálculo de KPIs sobre dados consolidados.

Produz métricas de faturamento, produtos e vendas para análise.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

import pandas as pd


def compute_kpis(df: pd.DataFrame, top_n: int = 10) -> dict:
    """Calcula KPIs básicos do pipeline.

    Args:
        df: DataFrame padronizado e consolidado.
        top_n: Quantos produtos incluir nos rankings.

    Returns:
        Dict com as métricas calculadas.
    """
    if df.empty:
        return {
            "total_faturamento_centavos": 0,
            "qtd_notas_fiscais": 0,
            "total_itens": 0,
            "quantidade_total": 0.0,
            "ticket_medio_centavos": 0,
            "faturamento_sem_data_centavos": 0,
            "itens_sem_data": 0,
            "top_produtos_valor": [],
            "top_produtos_qtd": [],
            "vendas_por_mes": [],
        }

    kpis = {}

    # Totais
    kpis["total_faturamento_centavos"] = int(
        cast(Any, df["valor_total_venda_centavos"].sum())
    )
    kpis["qtd_notas_fiscais"] = int(df["id_venda"].nunique())
    # Contagem de linhas de item, não soma de quantidade: uma nota com duas
    # quatro produtos tem 4 itens, independentemente da soma das quantidades.
    kpis["total_itens"] = len(df)
    kpis["quantidade_total"] = float(df["quantidade"].sum()) if "quantidade" in df else 0.0

    # Ticket médio
    if kpis["qtd_notas_fiscais"] > 0:
        kpis["ticket_medio_centavos"] = int(
            (
                Decimal(kpis["total_faturamento_centavos"])
                / Decimal(kpis["qtd_notas_fiscais"])
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    else:
        kpis["ticket_medio_centavos"] = 0

    # Top produtos por valor
    top_valor = (
        df.groupby(["codigo_produto", "descricao_produto"])["valor_total_venda_centavos"]
        .sum()
        .reset_index()
        .sort_values("valor_total_venda_centavos", ascending=False)
        .head(top_n)
    )
    kpis["top_produtos_valor"] = [
        {
            "codigo": r["codigo_produto"],
            "descricao": r["descricao_produto"],
            "total_centavos": int(cast(Any, r["valor_total_venda_centavos"])),
        }
        for _, r in top_valor.iterrows()
    ]

    # Top produtos por quantidade
    top_qtd = (
        df.groupby(["codigo_produto", "descricao_produto"])["quantidade"]
        .sum()
        .reset_index()
        .sort_values("quantidade", ascending=False)
        .head(top_n)
    )
    kpis["top_produtos_qtd"] = [
        {
            "codigo": r["codigo_produto"],
            "descricao": r["descricao_produto"],
            "total": float(r["quantidade"]),
        }
        for _, r in top_qtd.iterrows()
    ]

    # Vendas por mês.
    # Linhas sem data não entram na série — são contabilizadas à parte para
    # que a soma dos meses mais o residual feche com o faturamento total.
    df_mes = df.copy()
    df_mes["data_emissao"] = pd.to_datetime(df_mes["data_emissao"], errors="coerce")
    sem_data = df_mes["data_emissao"].isna()
    kpis["faturamento_sem_data_centavos"] = int(
        df_mes.loc[sem_data, "valor_total_venda_centavos"].sum()
    )
    kpis["itens_sem_data"] = int(sem_data.sum())
    df_mes = df_mes[~sem_data]

    if df_mes.empty:
        kpis["vendas_por_mes"] = []
        return kpis

    df_mes["ano_mes"] = df_mes["data_emissao"].dt.to_period("M").astype(str)
    vendas_mes = (
        df_mes.groupby("ano_mes")["valor_total_venda_centavos"]
        .sum()
        .reset_index()
        .sort_values("ano_mes")
    )
    kpis["vendas_por_mes"] = [
        {
            "mes": r["ano_mes"],
            "total_centavos": int(cast(Any, r["valor_total_venda_centavos"])),
        }
        for _, r in vendas_mes.iterrows()
    ]

    return kpis

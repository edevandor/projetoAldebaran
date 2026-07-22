"""Cálculo de KPIs sobre dados consolidados.

Produz métricas de faturamento, produtos e vendas para análise.
"""

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
            "total_faturamento": 0.0,
            "qtd_notas_fiscais": 0,
            "total_itens": 0,
            "ticket_medio": 0.0,
            "top_produtos_valor": [],
            "top_produtos_qtd": [],
            "vendas_por_mes": [],
        }

    kpis = {}

    # Totais
    kpis["total_faturamento"] = float(df["valor_total_venda"].sum())
    kpis["qtd_notas_fiscais"] = int(df["id_venda"].nunique())
    kpis["total_itens"] = len(df)

    # Ticket médio
    if kpis["qtd_notas_fiscais"] > 0:
        kpis["ticket_medio"] = round(
            kpis["total_faturamento"] / kpis["qtd_notas_fiscais"], 2
        )
    else:
        kpis["ticket_medio"] = 0.0

    # Top produtos por valor
    top_valor = (
        df.groupby(["codigo_produto", "descricao_produto"])["valor_total_venda"]
        .sum()
        .reset_index()
        .sort_values("valor_total_venda", ascending=False)
        .head(top_n)
    )
    kpis["top_produtos_valor"] = [
        {
            "codigo": r["codigo_produto"],
            "descricao": r["descricao_produto"],
            "total": float(r["valor_total_venda"]),
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

    # Vendas por mês
    df_mes = df.copy()
    df_mes["data_emissao"] = pd.to_datetime(df_mes["data_emissao"])
    df_mes["ano_mes"] = df_mes["data_emissao"].dt.to_period("M").astype(str)
    vendas_mes = (
        df_mes.groupby("ano_mes")["valor_total_venda"]
        .sum()
        .reset_index()
        .sort_values("ano_mes")
    )
    kpis["vendas_por_mes"] = [
        {"mes": r["ano_mes"], "total": float(r["valor_total_venda"])}
        for _, r in vendas_mes.iterrows()
    ]

    return kpis

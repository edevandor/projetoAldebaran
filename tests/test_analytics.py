"""Testes do módulo de analytics — cálculo de KPIs."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from analytics.kpis import compute_kpis


class TestComputeKPIs:
    """Suite de testes para os KPIs do pipeline."""

    def _df_base(self) -> pd.DataFrame:
        """DataFrame com 3 itens, 2 NFs diferentes."""
        return pd.DataFrame([
            {
                "codigo_produto": "0000001",
                "descricao_produto": "FERRAMENTA A",
                "id_venda": "001001-1000012025-01-15",
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 150.0,
                "quantidade": 2,
            },
            {
                "codigo_produto": "0000002",
                "descricao_produto": "FERRAMENTA B",
                "id_venda": "001001-1000012025-01-15",
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 300.0,
                "quantidade": 1,
            },
            {
                "codigo_produto": "0000003",
                "descricao_produto": "PARAFUSO C",
                "id_venda": "001001-1000022025-03-01",
                "data_emissao": date(2025, 3, 1),
                "valor_total_venda": 45.0,
                "quantidade": 10,
            },
        ])

    def test_total_faturamento(self):
        """SUM de valor_total_venda."""
        kpis = compute_kpis(self._df_base())
        assert kpis["total_faturamento"] == 495.0

    def test_qtd_notas_fiscais(self):
        """COUNT DISTINCT de id_venda."""
        kpis = compute_kpis(self._df_base())
        assert kpis["qtd_notas_fiscais"] == 2

    def test_total_itens(self):
        """COUNT de linhas."""
        kpis = compute_kpis(self._df_base())
        assert kpis["total_itens"] == 3

    def test_ticket_medio(self):
        """SUM(valor) / COUNT DISTINCT(id_venda)."""
        kpis = compute_kpis(self._df_base())
        assert kpis["ticket_medio"] == 247.5  # 495 / 2

    def test_top_produtos_quantidade(self):
        """Top 3 produtos por quantidade."""
        df = self._df_base()
        kpis = compute_kpis(df, top_n=3)
        assert len(kpis["top_produtos_qtd"]) == 3
        assert kpis["top_produtos_qtd"][0]["codigo"] == "0000003"  # qtd=10

    def test_top_produtos_valor(self):
        """Top produtos por valor."""
        df = self._df_base()
        kpis = compute_kpis(df, top_n=3)
        assert len(kpis["top_produtos_valor"]) == 3
        assert kpis["top_produtos_valor"][0]["codigo"] == "0000002"  # valor=300

    def test_vendas_por_mes(self):
        """Vendas agregadas por mês."""
        df = self._df_base()
        kpis = compute_kpis(df)
        assert "vendas_por_mes" in kpis
        assert len(kpis["vendas_por_mes"]) == 2  # 2 meses diferentes

    def test_dataframe_vazio(self):
        """DataFrame vazio retorna KPIs zerados."""
        df = pd.DataFrame(columns=["codigo_produto", "id_venda", "valor_total_venda", "quantidade", "data_emissao"])
        kpis = compute_kpis(df)
        assert kpis["total_faturamento"] == 0.0
        assert kpis["qtd_notas_fiscais"] == 0
        assert kpis["total_itens"] == 0

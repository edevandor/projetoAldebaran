"""Testes da camada de consulta SQL local sobre o Parquet publicado."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from export.formatters import export_to_parquet
from query.engine import CONSULTAS, consultar, listar_consultas


@pytest.fixture
def parquet(tmp_path: Path) -> Path:
    """Parquet publicado com duas notas — uma delas com dois itens."""
    df = pd.DataFrame([
        {
            "id_item_venda": "001-100001|2025-01-15|01",
            "id_venda": "001-100001|2025-01-15",
            "data_emissao": date(2025, 1, 15),
            "numero_documento": "001-100001",
            "codigo_produto": "000101",
            "descricao_produto": "PRODUTO ALFA",
            "quantidade": 2.0,
            "valor_total_venda": 1000.0,
            "valor_total_venda_centavos": 100000,
            "responsavel": "Carlos Silva",
        },
        {
            "id_item_venda": "001-100001|2025-01-15|02",
            "id_venda": "001-100001|2025-01-15",
            "data_emissao": date(2025, 1, 15),
            "numero_documento": "001-100001",
            "codigo_produto": "000204",
            "descricao_produto": "PRODUTO BETA",
            "quantidade": 4.0,
            "valor_total_venda": 500.0,
            "valor_total_venda_centavos": 50000,
            "responsavel": "Carlos Silva",
        },
        {
            "id_item_venda": "001-100002|2025-03-10|01",
            "id_venda": "001-100002|2025-03-10",
            "data_emissao": date(2025, 3, 10),
            "numero_documento": "001-100002",
            "codigo_produto": "000101",
            "descricao_produto": "PRODUTO ALFA",
            "quantidade": 1.0,
            "valor_total_venda": 800.0,
            "valor_total_venda_centavos": 80000,
            "responsavel": "Ana Oliveira",
        },
    ])
    df["id_execucao"] = "run-test"
    df["tipo_documento"] = "001"
    df["arquivo_origem"] = "teste.xlsx"
    df["sistema_origem"] = "ATUAL"
    df["confianca_data"] = "Registrada"
    df["confianca_identidade"] = "Observada"
    return export_to_parquet(df, tmp_path / "vendas.parquet")


class TestConsultar:
    def test_sql_ad_hoc(self, parquet: Path):
        resultado = consultar("SELECT COUNT(*) AS n FROM vendas", parquet_path=parquet)
        assert resultado["n"].iloc[0] == 3

    def test_view_sql_expoe_valor_em_reais(self, parquet: Path):
        resultado = consultar(
            "SELECT SUM(valor_total_venda) AS total FROM vendas",
            parquet_path=parquet,
        )

        assert resultado["total"].iloc[0] == 2300.0

    def test_filtro_por_data_sem_cast(self, parquet: Path):
        """A tipagem temporal do Parquet permite filtrar por data diretamente."""
        resultado = consultar(
            "SELECT COUNT(*) AS n FROM vendas WHERE data_emissao >= DATE '2025-02-01'",
            parquet_path=parquet,
        )
        assert resultado["n"].iloc[0] == 1

    def test_agregacao_por_mes(self, parquet: Path):
        resultado = consultar("sazonalidade", parquet_path=parquet)
        assert len(resultado) == 2
        assert resultado["faturamento"].sum() == 2300.0

    def test_notas_contadas_por_id_venda(self, parquet: Path):
        """Duas linhas da mesma nota contam como uma venda."""
        resultado = consultar("cobertura", parquet_path=parquet)
        assert resultado["itens"].iloc[0] == 3
        assert resultado["notas"].iloc[0] == 2

    def test_consultas_prontas_executam(self, parquet: Path):
        for nome in listar_consultas():
            assert consultar(nome, parquet_path=parquet) is not None

    def test_parquet_inexistente_orienta_o_utilizador(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="aldebaran run"):
            consultar("SELECT 1", parquet_path=tmp_path / "nao_existe.parquet")


class TestCatalogoDeConsultas:
    def test_listagem_ordenada(self):
        assert listar_consultas() == sorted(CONSULTAS)

    def test_consultas_referenciam_a_tabela_publicada(self):
        for sql in CONSULTAS.values():
            assert "FROM vendas" in sql or "FROM (" in sql

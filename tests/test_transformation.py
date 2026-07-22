"""Testes do módulo de transformação — padronização de dados."""

from datetime import date
from ingestion.parser import parse_xlsx
from ingestion.directory import ingest_directory
from transformation.standardizer import standardize
import pandas as pd
from pathlib import Path
import pytest


class TestStandardize:
    """Suite de testes para a padronização de dados."""

    def _df_base(self) -> pd.DataFrame:
        """DataFrame mínimo para testes."""
        return pd.DataFrame([
            {
                "produto": "0000001 - FERRAMENTA A 150MM",
                "data_emissao": date(2025, 1, 15),
                "tipo_documento": "001",
                "numero_documento": "001-100001",
                "protocolo": "20250000000000001",
                "valor_total_venda": 150.0,
                "quantidade": 2,
                "unidade_medida": "UN",
                "arquivo_origem": "teste.xlsx",
            }
        ])

    def test_separa_codigo_e_descricao(self):
        """standardize separa 'produto' em codigo_produto e descricao_produto."""
        df = self._df_base()
        resultado = standardize(df)
        assert resultado["codigo_produto"].iloc[0] == "0000001"
        assert resultado["descricao_produto"].iloc[0] == "FERRAMENTA A 150MM"

    def test_gera_id_venda(self):
        """id_venda = tipo_documento + numero_documento + data_emissao."""
        df = self._df_base()
        resultado = standardize(df)
        assert resultado["id_venda"].iloc[0] == "001001-1000012025-01-15"

    def test_gera_id_item_venda(self):
        """id_item_venda = id_venda + protocolo."""
        df = self._df_base()
        resultado = standardize(df)
        esperado = "001001-1000012025-01-1520250000000000001"
        assert resultado["id_item_venda"].iloc[0] == esperado

    def test_mantem_colunas_originais(self):
        """Colunas originais permanecem após padronização."""
        df = self._df_base()
        cols_originais = set(df.columns)
        resultado = standardize(df)
        assert cols_originais.issubset(set(resultado.columns))

    def test_produto_sem_separador_mantem_inteiro(self):
        """Produto sem ' - ' mantém codigo vazio e descricao = produto."""
        df = pd.DataFrame([{"produto": "SERVICO DE MANUTENCAO", "data_emissao": date(2025,1,1),
                            "tipo_documento": "001", "numero_documento": "001-000001",
                            "protocolo": "", "valor_total_venda": 500.0, "quantidade": 1,
                            "unidade_medida": "", "arquivo_origem": "x.xlsx"}])
        resultado = standardize(df)
        assert resultado["codigo_produto"].iloc[0] == ""
        assert resultado["descricao_produto"].iloc[0] == "SERVICO DE MANUTENCAO"

    def test_funciona_com_output_do_parser(self):
        """standardize aceita o output real do parse_xlsx."""
        path = Path(__file__).parent / "fixtures" / "mapa_vendas_teste.xlsx"
        dados = parse_xlsx(path)
        df = pd.DataFrame(dados)
        resultado = standardize(df)
        assert "codigo_produto" in resultado.columns
        assert "id_venda" in resultado.columns
        assert "id_item_venda" in resultado.columns
        assert len(resultado) == 5

    def test_colunas_novas_nao_substituem_existentes(self):
        """Campos novos (codigo_produto, id_venda, id_item_venda) não apagam
        campos existentes com mesmo nome de coluna."""
        df = self._df_base()
        resultado = standardize(df)
        # Todos os campos originais ainda existem
        for col in ["produto", "data_emissao", "tipo_documento",
                     "numero_documento", "protocolo", "valor_total_venda"]:
            assert col in resultado.columns, f"Coluna {col} foi perdida"

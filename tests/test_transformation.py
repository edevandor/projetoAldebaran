"""Testes do módulo de transformação — padronização de dados."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ingestion.parser import parse_xlsx
from transformation.money import to_centavos
from transformation.standardizer import standardize


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
                "sistema_origem": "ATUAL",
            }
        ])

    def test_separa_codigo_e_descricao(self):
        """standardize separa 'produto' em codigo_produto e descricao_produto."""
        df = self._df_base()
        resultado = standardize(df)
        assert resultado["codigo_produto"].iloc[0] == "0000001"
        assert resultado["descricao_produto"].iloc[0] == "FERRAMENTA A 150MM"

    def test_gera_id_venda(self):
        """id_venda = numero_documento | data_emissao, com separador explícito."""
        df = self._df_base()
        resultado = standardize(df)
        assert resultado["id_venda"].iloc[0] == "ATUAL|001-100001|2025-01-15"

    def test_gera_id_item_venda(self):
        """id_item_venda = id_venda | protocolo."""
        df = self._df_base()
        resultado = standardize(df)
        esperado = "ATUAL|001-100001|2025-01-15|20250000000000001"
        assert resultado["id_item_venda"].iloc[0] == esperado

    def test_namespace_da_origem_impede_colisao_entre_sistemas(self):
        atual = self._df_base().iloc[0].to_dict()
        atual["sistema_origem"] = "ATUAL"
        legado = {**atual, "sistema_origem": "LEGADO", "arquivo_origem": "vendas.rel"}

        resultado = standardize(pd.DataFrame([atual, legado]))

        assert resultado["id_item_venda"].nunique() == 2
        assert set(resultado["id_item_venda"].str.split("|").str[0]) == {"ATUAL", "LEGADO"}

    def test_chave_e_reversivel(self):
        """A chave pode ser decomposta de volta nos seus componentes."""
        df = self._df_base()
        resultado = standardize(df)
        sistema, documento, data, protocolo = resultado["id_item_venda"].iloc[0].split("|")
        assert sistema == "ATUAL"
        assert documento == "001-100001"
        assert data == "2025-01-15"
        assert protocolo == "20250000000000001"

    def test_data_ausente_marcada_na_chave(self):
        """Sem data, a chave registra SEM_DATA em vez de 'None'."""
        df = self._df_base()
        df.loc[0, "data_emissao"] = None
        resultado = standardize(df)
        assert resultado["id_venda"].iloc[0] == "ATUAL|001-100001|SEM_DATA"

    def test_mantem_colunas_originais(self):
        """Colunas originais permanecem após padronização."""
        df = self._df_base()
        cols_originais = set(df.columns)
        resultado = standardize(df)
        assert cols_originais.issubset(set(resultado.columns))

    def test_valor_monetario_e_canonizado_em_centavos(self):
        df = self._df_base()

        resultado = standardize(df)

        assert resultado["valor_total_venda_centavos"].iloc[0] == 15000

    def test_identidade_sem_protocolo_independe_da_proveniencia(self):
        primeira = self._df_base()
        primeira.loc[0, "protocolo"] = ""
        primeira["arquivo_origem"] = "arquivo_a.xlsx"
        primeira["linha_origem"] = 10
        segunda = primeira.copy()
        segunda["arquivo_origem"] = "arquivo_renomeado.xlsx"
        segunda["linha_origem"] = 99

        chave_primeira = standardize(primeira)["id_item_venda"].iloc[0]
        chave_segunda = standardize(segunda)["id_item_venda"].iloc[0]

        assert chave_primeira == chave_segunda
        assert "SEM_PROTOCOLO" in chave_primeira

    def test_identidade_inferida_e_declarada(self):
        df = self._df_base()
        df.loc[0, "protocolo"] = ""

        resultado = standardize(df)

        assert resultado["confianca_identidade"].iloc[0] == "Derivada (sem protocolo)"

    @pytest.mark.parametrize("valor", [None, "invalido"])
    def test_valor_monetario_nao_conversivel_fica_ausente_para_quarentena(self, valor):
        df = self._df_base()
        df["valor_total_venda"] = df["valor_total_venda"].astype("object")
        df.loc[0, "valor_total_venda"] = valor

        resultado = standardize(df)

        assert pd.isna(resultado["valor_total_venda_centavos"].iloc[0])

    def test_produto_sem_separador_mantem_inteiro(self):
        """Produto sem ' - ' mantém codigo vazio e descricao = produto."""
        df = pd.DataFrame([{"produto": "SERVICO DE MANUTENCAO", "data_emissao": date(2025,1,1),
                            "tipo_documento": "001", "numero_documento": "001-000001",
                            "protocolo": "", "valor_total_venda": 500.0, "quantidade": 1,
                            "unidade_medida": "", "arquivo_origem": "x.xlsx",
                            "sistema_origem": "ATUAL"}])
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


class TestCentavos:
    def test_converte_numero_brasileiro_sem_passar_por_float(self):
        assert to_centavos("1.234,56") == 123456

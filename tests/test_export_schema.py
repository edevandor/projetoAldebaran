"""Testes do contrato de saída — schema canónico, Parquet e CSV."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from export.formatters import export_to_csv, export_to_parquet
from export.schema import SCHEMA_SAIDA, aplicar_schema


@pytest.fixture
def df_consolidado() -> pd.DataFrame:
    """DataFrame como sai da consolidação: com colunas intermediárias."""
    return pd.DataFrame([
        {
            "produto": "000101 - PRODUTO ALFA MODELO 100",
            "id_execucao": "run-test",
            "codigo_produto": "000101",
            "descricao_produto": "PRODUTO ALFA MODELO 100",
            "data_emissao": date(2025, 1, 15),
            "tipo_documento": "001",
            "numero_documento": "001-100001",
            "protocolo": "000101",
            "id_venda": "001-100001|2025-01-15",
            "id_item_venda": "001-100001|2025-01-15|000101",
            "valor_total_venda": 1500.5,
            "valor_total_venda_centavos": 150050,
            "quantidade": 2.0,
            "unidade_medida": "UN",
            "responsavel": "Carlos Silva",
            "artigo": "Venda Direta",
            "arquivo_origem": "vendas.xlsx",
            "sistema_origem": "ATUAL",
            "confianca_data": "Registrada",
            "confianca_identidade": "Observada",
            "coluna_extra_do_meio_do_caminho": "descartar",
        }
    ])


class TestSchema:
    """O schema é o contrato único das duas camadas de saída."""

    def test_colunas_seguem_o_schema(self, df_consolidado):
        resultado = aplicar_schema(df_consolidado)
        assert list(resultado.columns) == list(SCHEMA_SAIDA)

    def test_descarta_coluna_produto_redundante(self, df_consolidado):
        """`produto` é codigo + descrição, ambos já publicados."""
        resultado = aplicar_schema(df_consolidado)
        assert "produto" not in resultado.columns
        assert "codigo_produto" in resultado.columns
        assert "descricao_produto" in resultado.columns

    def test_descarta_colunas_fora_do_contrato(self, df_consolidado):
        resultado = aplicar_schema(df_consolidado)
        assert "coluna_extra_do_meio_do_caminho" not in resultado.columns

    def test_data_tipada_como_temporal(self, df_consolidado):
        """Data como tipo temporal, não string — permite filtro em SQL sem CAST."""
        resultado = aplicar_schema(df_consolidado)
        assert pd.api.types.is_datetime64_any_dtype(resultado["data_emissao"])

    def test_valores_tipados_como_numero(self, df_consolidado):
        resultado = aplicar_schema(df_consolidado)
        assert pd.api.types.is_float_dtype(resultado["quantidade"])

    def test_valor_monetario_canonico_e_inteiro_em_centavos(self, df_consolidado):
        resultado = aplicar_schema(df_consolidado)

        assert resultado["valor_total_venda_centavos"].iloc[0] == 150050
        assert pd.api.types.is_integer_dtype(resultado["valor_total_venda_centavos"])
        assert "valor_total_venda" not in resultado.columns

    def test_publica_confianca_da_identidade(self, df_consolidado):
        resultado = aplicar_schema(df_consolidado)

        assert resultado["confianca_identidade"].iloc[0] == "Observada"

    def test_coluna_ausente_e_criada_vazia(self, df_consolidado):
        """Contrato estável mesmo quando a origem não traz todos os campos."""
        parcial = df_consolidado.drop(columns=["responsavel"])
        resultado = aplicar_schema(parcial)
        assert list(resultado.columns) == list(SCHEMA_SAIDA)
        assert resultado["responsavel"].isna().all()

    def test_coluna_obrigatoria_ausente_viola_o_contrato(self, df_consolidado):
        parcial = df_consolidado.drop(columns=["id_execucao"])

        with pytest.raises(ValueError, match="id_execucao"):
            aplicar_schema(parcial)

    def test_valor_obrigatorio_incoercivel_viola_o_contrato(self, df_consolidado):
        invalido = df_consolidado.copy()
        invalido["valor_total_venda_centavos"] = "invalido"

        with pytest.raises(ValueError, match="valor_total_venda_centavos"):
            aplicar_schema(invalido)

    def test_dataframe_vazio_preserva_contrato(self):
        resultado = aplicar_schema(pd.DataFrame())
        assert list(resultado.columns) == list(SCHEMA_SAIDA)
        assert len(resultado) == 0


class TestParquet:
    """Parquet é o formato principal: tipado e consultável."""

    def test_cria_arquivo(self, df_consolidado, tmp_path: Path):
        destino = export_to_parquet(df_consolidado, tmp_path / "vendas.parquet")
        assert destino.exists()

    def test_roundtrip_preserva_tipos(self, df_consolidado, tmp_path: Path):
        destino = export_to_parquet(df_consolidado, tmp_path / "vendas.parquet")
        lido = pd.read_parquet(destino)
        assert list(lido.columns) == list(SCHEMA_SAIDA)
        assert pd.api.types.is_datetime64_any_dtype(lido["data_emissao"])
        assert lido["data_emissao"].iloc[0] == pd.Timestamp("2025-01-15")

    def test_parquet_declara_nulabilidade_fisica(self, df_consolidado, tmp_path: Path):
        import pyarrow.parquet as pq

        destino = export_to_parquet(df_consolidado, tmp_path / "vendas.parquet")
        schema = pq.read_schema(destino)

        assert not schema.field("id_execucao").nullable
        assert not schema.field("valor_total_venda_centavos").nullable
        assert schema.field("data_emissao").nullable

    def test_cria_diretorio_intermediario(self, df_consolidado, tmp_path: Path):
        destino = export_to_parquet(df_consolidado, tmp_path / "sub" / "v.parquet")
        assert destino.exists()


class TestCSV:
    """CSV é a exportação secundária, com o mesmo schema."""

    def test_cabecalho_segue_o_schema(self, df_consolidado, tmp_path: Path):
        destino = export_to_csv(df_consolidado, tmp_path / "vendas.csv")
        cabecalho = destino.read_text(encoding="utf-8").splitlines()[0]
        assert cabecalho == ",".join(SCHEMA_SAIDA)

    def test_data_em_formato_iso(self, df_consolidado, tmp_path: Path):
        destino = export_to_csv(df_consolidado, tmp_path / "vendas.csv")
        assert "2025-01-15" in destino.read_text(encoding="utf-8").splitlines()[1]

    def test_valor_monetario_em_centavos(self, df_consolidado, tmp_path: Path):
        destino = export_to_csv(df_consolidado, tmp_path / "vendas.csv")
        assert "150050" in destino.read_text(encoding="utf-8")

    def test_utf8_sem_bom(self, df_consolidado, tmp_path: Path):
        destino = export_to_csv(df_consolidado, tmp_path / "vendas.csv")
        assert not destino.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_vazio_gera_so_cabecalho(self, tmp_path: Path):
        destino = export_to_csv(pd.DataFrame(), tmp_path / "vazio.csv")
        linhas = destino.read_text(encoding="utf-8").strip().splitlines()
        assert len(linhas) == 1

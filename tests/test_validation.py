"""Testes do módulo de validação — regras de negócio e integridade."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from validation.validator import validate, ValidationReport


class TestValidationReport:
    """Suite de testes para o relatório de validação."""

    def _df_valido(self) -> pd.DataFrame:
        """DataFrame com dados válidos."""
        from transformation.standardizer import standardize
        base = pd.DataFrame([{
            "produto": "0000001 - FERRAMENTA A 150MM",
            "data_emissao": date(2025, 1, 15),
            "tipo_documento": "001",
            "numero_documento": "001-100001",
            "protocolo": "20250000000000001",
            "valor_total_venda": 150.0,
            "quantidade": 2,
            "unidade_medida": "UN",
            "arquivo_origem": "teste.xlsx",
        }])
        return standardize(base)

    def test_dados_validos_retorna_sem_erros(self):
        """DataFrame válido não gera erros."""
        df = self._df_valido()
        relatorio = validate(df)
        assert not relatorio.has_errors
        assert len(relatorio.errors) == 0

    def test_campo_obrigatorio_ausente_gera_erro(self):
        """data_emissao nula gera erro."""
        df = self._df_valido()
        df.loc[0, "data_emissao"] = None
        relatorio = validate(df)
        assert relatorio.has_errors
        assert any("data_emissao" in e for e in relatorio.errors)

    def test_produto_vazio_gera_erro(self):
        """produto vazio gera erro."""
        df = self._df_valido()
        df.loc[0, "produto"] = ""
        relatorio = validate(df)
        assert relatorio.has_errors

    def test_numero_documento_vazio_gera_erro(self):
        """numero_documento vazio gera erro."""
        df = self._df_valido()
        df.loc[0, "numero_documento"] = ""
        relatorio = validate(df)
        assert relatorio.has_errors

    def test_valor_venda_zerado_aceito(self):
        """valor_total_venda = 0 é aceito (pode ser cortesia/amostra)."""
        df = self._df_valido()
        df.loc[0, "valor_total_venda"] = 0.0
        relatorio = validate(df)
        assert not relatorio.has_errors

    def test_duplicata_id_venda_gera_erro(self):
        """Duas linhas com o mesmo id_venda geram erro."""
        df = self._df_valido()
        df2 = df.copy()
        df2.loc[0, "quantidade"] = 5  # mesmo id_venda, qtd diferente
        df_dup = pd.concat([df, df2], ignore_index=True)
        relatorio = validate(df_dup)
        assert relatorio.has_errors
        assert any("duplicata" in e.lower() or "id_venda" in e for e in relatorio.errors)

    def test_total_rows_no_relatorio(self):
        """Relatório informa o total de linhas validadas."""
        df = self._df_valido()
        relatorio = validate(df)
        assert relatorio.total_rows == 1

    def test_summary_string(self):
        """summary() retorna string legível."""
        df = self._df_valido()
        relatorio = validate(df)
        resumo = relatorio.summary()
        assert isinstance(resumo, str)
        assert "OK" in resumo

    def test_summary_com_erros(self):
        """summary() com erros mostra contagem."""
        df = self._df_valido()
        df.loc[0, "data_emissao"] = None
        df.loc[0, "produto"] = ""
        relatorio = validate(df)
        resumo = relatorio.summary()
        assert isinstance(resumo, str)
        assert str(relatorio.total_errors()) in resumo

    def test_funciona_com_output_real_do_pipeline(self):
        """validate aceita dados de exemplo do parser + standardizer."""
        from ingestion.parser import parse_xlsx
        from transformation.standardizer import standardize

        path = Path(__file__).parent / "fixtures" / "mapa_vendas_teste.xlsx"
        dados = parse_xlsx(path)
        df = pd.DataFrame(dados)
        df = standardize(df)
        relatorio = validate(df)
        # Dados sintéticos são válidos
        assert not relatorio.has_errors
        assert relatorio.total_rows == 5

    def test_protocolo_vazio_nao_gera_erro(self):
        """Protocolo vazio é aceito (campo condicional)."""
        df = self._df_valido()
        df.loc[0, "protocolo"] = ""
        relatorio = validate(df)
        assert not relatorio.has_errors

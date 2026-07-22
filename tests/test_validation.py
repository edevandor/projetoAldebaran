"""Testes do módulo de validação — regras de negócio e integridade."""

from datetime import date
from pathlib import Path

import pandas as pd

from transformation.standardizer import standardize
from validation.validator import validate


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
            "sistema_origem": "ATUAL",
            "confianca_data": "Registrada",
            "id_execucao": "run-test",
        }])
        return standardize(base)

    def test_dados_validos_retorna_sem_erros(self):
        """DataFrame válido não gera erros."""
        df = self._df_valido()
        relatorio = validate(df)
        assert not relatorio.has_errors
        assert len(relatorio.errors) == 0

    def test_data_ausente_gera_aviso_nao_erro(self):
        """Linha sem data é sinalizada, mas não invalida o dataset.

        A migração de servidor de 2023 deixou vendas sem datação:
        descartá-las perderia venda real.
        """
        df = self._df_valido()
        df.loc[0, "data_emissao"] = None
        relatorio = validate(df)
        assert not relatorio.has_errors
        assert any("data_emissao" in a for a in relatorio.warnings)

    def test_campo_obrigatorio_ausente_gera_erro(self):
        """Coluna obrigatória inexistente gera erro."""
        df = self._df_valido().drop(columns=["numero_documento"])
        relatorio = validate(df)
        assert relatorio.has_errors
        assert any("numero_documento" in e for e in relatorio.errors)

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

    def test_duplicata_id_item_venda_gera_erro(self):
        """Duas linhas com o mesmo id_item_venda geram erro."""
        df = self._df_valido()
        df2 = df.copy()
        df2.loc[0, "quantidade"] = 5  # mesmo item da mesma nota, qtd diferente
        df_dup = pd.concat([df, df2], ignore_index=True)
        relatorio = validate(df_dup)
        assert relatorio.has_errors
        assert any("id_item_venda" in e for e in relatorio.errors)

    def test_mesma_nota_com_varios_itens_e_valida(self):
        """Uma nota com vários itens repete id_venda sem gerar erro.

        Regra de negócio: a granularidade do dataset é o item, e uma venda
        de quatro produtos produz quatro linhas na mesma nota.
        """
        df = self._df_valido()
        segundo_item = df.copy()
        segundo_item.loc[0, "protocolo"] = "20250000000000002"
        segundo_item.loc[0, "produto"] = "0000002 - FERRAMENTA B 200MM"
        nota = pd.concat([df, standardize(segundo_item)], ignore_index=True)

        relatorio = validate(nota)

        assert nota["id_venda"].nunique() == 1
        assert nota["id_item_venda"].nunique() == 2
        assert not relatorio.has_errors

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


class TestParticaoDoContrato:
    def test_registro_invalido_e_separado_sem_contaminar_os_validos(self):
        from validation.validator import validate_and_partition

        valido = TestValidationReport()._df_valido()
        invalido = valido.copy()
        invalido.loc[0, "numero_documento"] = ""
        entrada = pd.concat([valido, invalido], ignore_index=True)

        aceitos, rejeitados, relatorio = validate_and_partition(entrada)

        assert len(aceitos) == 1
        assert len(rejeitados) == 1
        assert rejeitados["codigo_rejeicao"].iloc[0] == "CAMPO_OBRIGATORIO_VAZIO"
        assert relatorio.rejected_rows == 1

    def test_coluna_estrutural_ausente_nao_vira_rejeicao_de_linha(self):
        from validation.validator import validate_and_partition

        entrada = TestValidationReport()._df_valido().drop(columns=["sistema_origem"])

        aceitos, rejeitados, relatorio = validate_and_partition(entrada)

        assert aceitos.empty
        assert rejeitados.empty
        assert relatorio.structural_errors == ["Campo obrigatório ausente: sistema_origem"]

    def test_chave_duplicada_rejeita_todas_as_ocorrencias(self):
        from validation.validator import validate_and_partition

        linha = TestValidationReport()._df_valido()
        entrada = pd.concat([linha, linha], ignore_index=True)

        aceitos, rejeitados, _ = validate_and_partition(entrada)

        assert aceitos.empty
        assert len(rejeitados) == 2
        assert set(rejeitados["codigo_rejeicao"]) == {"CHAVE_DUPLICADA"}

    def test_data_ausente_e_aceita_com_aviso(self):
        from validation.validator import validate_and_partition

        entrada = TestValidationReport()._df_valido()
        entrada.loc[0, "data_emissao"] = None

        aceitos, rejeitados, relatorio = validate_and_partition(entrada)

        assert len(aceitos) == 1
        assert rejeitados.empty
        assert relatorio.warnings == ["1 linha(s) sem data_emissao"]

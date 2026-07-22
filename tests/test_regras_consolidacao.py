"""Testes das regras que decidem a identidade e a versão de cada venda.

Cada caso aqui corresponde a uma situação real da operação: relatórios
reexportados, registros sem data e o mesmo arquivo lido duas vezes.
"""

from datetime import date

import pandas as pd
import pytest

from analytics.kpis import compute_kpis
from consolidation.consolidator import consolidate, resolve_versoes
from transformation.standardizer import standardize

BASE = {
    "produto": "000101 - PRODUTO ALFA",
    "tipo_documento": "001",
    "numero_documento": "001-100001",
    "protocolo": "01",
    "quantidade": 1.0,
    "unidade_medida": "UN",
    "responsavel": "Carlos",
    "artigo": "Venda Direta",
    "sistema_origem": "ATUAL",
}


def _executar(linhas: list[dict]) -> tuple[pd.DataFrame, int, dict]:
    """Roda as etapas do pipeline que decidem identidade e versão."""
    df = pd.DataFrame(linhas)
    df, _ = consolidate(df)
    df = standardize(df)
    colisoes = df.attrs.get("colisoes_chave", 0)
    df, relatorio = resolve_versoes(df)
    return df, colisoes, relatorio


class TestReprocessamentoDePeriodo:
    """Relatório parcial seguido da versão consolidada do mesmo período."""

    @pytest.fixture
    def linhas(self) -> list[dict]:
        return [
            {**BASE, "data_emissao": date(2025, 1, 15), "valor_total_venda": 1000.00,
             "arquivo_origem": "2025_Q1_parcial.xlsx"},
            {**BASE, "data_emissao": date(2025, 1, 15), "valor_total_venda": 1000.01,
             "arquivo_origem": "2025_Q1_final.xlsx"},
        ]

    def test_nao_conta_o_faturamento_duas_vezes(self, linhas):
        df, _, _ = _executar(linhas)
        assert compute_kpis(df)["total_faturamento_centavos"] == 100001

    def test_mantem_uma_unica_versao_do_item(self, linhas):
        df, _, relatorio = _executar(linhas)
        assert len(df) == 1
        assert relatorio["versoes_substituidas"] == 1

    def test_prevalece_a_versao_mais_recente(self, linhas):
        df, _, _ = _executar(linhas)
        assert df["arquivo_origem"].iloc[0] == "2025_Q1_final.xlsx"

    def test_relatorio_aponta_os_arquivos_em_conflito(self, linhas):
        _, _, relatorio = _executar(linhas)
        assert relatorio["arquivos"] == ["2025_Q1_final.xlsx", "2025_Q1_parcial.xlsx"]


class TestPrecedenciaPorCobertura:
    """A versão é decidida pelo período do relatório, nunca pelo nome ou pela ordem."""

    def test_periodo_mais_recente_vence_mesmo_lido_primeiro(self):
        linhas = [
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 1000.01,
                "arquivo_origem": "a_final.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 3, 31),
            },
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 1000.00,
                "arquivo_origem": "z_parcial.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 3, 15),
            },
        ]

        df, _, _ = _executar(linhas)

        assert df["arquivo_origem"].iloc[0] == "a_final.xlsx"

    def test_empate_de_periodo_com_conteudo_diferente_nao_escolhe_vencedor(self):
        linhas = [
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 1000.00,
                "arquivo_origem": "extracao_a.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 3, 31),
            },
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 999.00,
                "arquivo_origem": "extracao_b.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 3, 31),
            },
        ]

        df, _, relatorio = _executar(linhas)

        assert df.empty
        assert len(relatorio["conflitos"]) == 2

    def test_empate_na_versao_mais_recente_nao_ressuscita_versao_antiga(self):
        linhas = [
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 900.00,
                "arquivo_origem": "versao_antiga.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 1, 31),
            },
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 1000.00,
                "arquivo_origem": "extracao_recente_a.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 3, 31),
            },
            {
                **BASE,
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 999.00,
                "arquivo_origem": "extracao_recente_b.xlsx",
                "periodo_inicio": date(2025, 1, 1),
                "periodo_fim": date(2025, 3, 31),
            },
        ]

        df, _, relatorio = _executar(linhas)

        assert df.empty
        assert len(relatorio["conflitos"]) == 3


class TestVendasSemData:
    """Registros que a migração de 2023 deixou sem datação."""

    @pytest.fixture
    def linhas(self) -> list[dict]:
        return [
            {**BASE, "data_emissao": None, "valor_total_venda": 100.0,
             "arquivo_origem": "q1.xlsx"},
            {**BASE, "data_emissao": None, "valor_total_venda": 999.0,
             "arquivo_origem": "q1.xlsx"},
        ]

    def test_vendas_distintas_nao_colapsam(self, linhas):
        """Sem data, duas vendas gerariam a mesma chave — e uma se perderia."""
        df, colisoes, _ = _executar(linhas)
        assert len(df) == 2
        assert colisoes == 1
        assert df["id_item_venda"].nunique() == 2

    def test_faturamento_preservado(self, linhas):
        df, _, _ = _executar(linhas)
        assert compute_kpis(df)["total_faturamento_centavos"] == 109900

    def test_chave_sinaliza_a_desambiguacao(self, linhas):
        df, _, _ = _executar(linhas)
        assert df["id_item_venda"].iloc[0] == "ATUAL|001-100001|SEM_DATA|01"
        assert df["id_item_venda"].iloc[1] == "ATUAL|001-100001|SEM_DATA|01#2"


class TestProtocoloAusente:
    def test_identidade_derivada_permite_resolver_reexportacao(self):
        linhas = [
            {
                **BASE,
                "protocolo": "",
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 100.0,
                "arquivo_origem": "a.xlsx",
                "linha_origem": 10,
                "periodo_fim": date(2025, 1, 31),
            },
            {
                **BASE,
                "protocolo": "",
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 999.0,
                "arquivo_origem": "b.xlsx",
                "linha_origem": 20,
                "periodo_fim": date(2025, 2, 28),
            },
        ]

        df, _, relatorio = _executar(linhas)

        assert len(df) == 1
        assert df["id_item_venda"].is_unique
        assert df["arquivo_origem"].iloc[0] == "b.xlsx"
        assert set(df["confianca_identidade"]) == {"Derivada (sem protocolo)"}
        assert relatorio["versoes_substituidas"] == 1


class TestLinhaIdentica:
    """O mesmo arquivo processado duas vezes, ou a mesma linha em dois arquivos."""

    def test_duplicata_exata_e_removida(self):
        linhas = [
            {**BASE, "data_emissao": date(2025, 1, 15), "valor_total_venda": 500.0,
             "arquivo_origem": "a.xlsx"},
            {**BASE, "data_emissao": date(2025, 1, 15), "valor_total_venda": 500.0,
             "arquivo_origem": "b.xlsx"},
        ]
        df, colisoes, relatorio = _executar(linhas)
        assert len(df) == 1
        assert colisoes == 0
        assert relatorio["versoes_substituidas"] == 0


class TestTotaisFecham:
    """A soma da série mensal mais o residual tem de dar o faturamento total."""

    def test_soma_dos_meses_mais_sem_data_fecha_com_o_total(self):
        linhas = [
            {**BASE, "data_emissao": date(2025, 1, 15), "valor_total_venda": 100.0,
             "arquivo_origem": "q1.xlsx"},
            {**BASE, "protocolo": "02", "data_emissao": None, "valor_total_venda": 250.0,
             "arquivo_origem": "q1.xlsx"},
        ]
        df, _, _ = _executar(linhas)
        kpis = compute_kpis(df)

        soma_meses = sum(m["total_centavos"] for m in kpis["vendas_por_mes"])
        assert (
            soma_meses + kpis["faturamento_sem_data_centavos"]
            == kpis["total_faturamento_centavos"]
        )
        assert kpis["itens_sem_data"] == 1

    def test_itens_e_quantidade_sao_metricas_distintas(self):
        linhas = [
            {**BASE, "data_emissao": date(2025, 1, 15), "quantidade": 4.0,
             "valor_total_venda": 100.0, "arquivo_origem": "q1.xlsx"},
        ]
        df, _, _ = _executar(linhas)
        kpis = compute_kpis(df)
        assert kpis["total_itens"] == 1        # linhas de item
        assert kpis["quantidade_total"] == 4.0  # unidades vendidas

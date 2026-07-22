"""Testes da união entre o ERP atual e o legado numa única base.

É a promessa central do projeto: um histórico contínuo, atravessando a
troca de sistema. Estes testes verificam que ela se sustenta na execução,
e não apenas na documentação.
"""

from datetime import date
from pathlib import Path

import pytest

from demo.gerador_rel import gerar_rel_analitico, gerar_rel_compras, gerar_rel_sintetico
from demo.gerador_xlsx import gerar_xlsx
from ingestion.legado import (
    COMPRAS,
    VENDAS_ANALITICO,
    VENDAS_SINTETICO,
    detectar_tipo,
    ingest_legado,
)
from pipeline import run_pipeline


@pytest.fixture
def origem(tmp_path: Path) -> Path:
    """Diretório com o relatório atual e os três formatos do legado."""
    gerar_xlsx(tmp_path / "raw" / "vendas.xlsx")
    gerar_rel_analitico(tmp_path / "legado" / "vendas_analitico.rel")
    gerar_rel_sintetico(tmp_path / "legado" / "vendas_sintetico.rel")
    gerar_rel_compras(tmp_path / "legado" / "compras_analitico.rel")
    return tmp_path


class TestDeteccaoDeTipo:
    """Os três relatórios têm o mesmo sufixo e propósitos diferentes."""

    def test_reconhece_vendas_analitico(self, origem: Path):
        assert detectar_tipo(origem / "legado" / "vendas_analitico.rel") == VENDAS_ANALITICO

    def test_reconhece_vendas_sintetico(self, origem: Path):
        assert detectar_tipo(origem / "legado" / "vendas_sintetico.rel") == VENDAS_SINTETICO

    def test_reconhece_compras(self, origem: Path):
        assert detectar_tipo(origem / "legado" / "compras_analitico.rel") == COMPRAS


class TestIngestaoDoLegado:
    def test_ingere_apenas_o_analitico_de_vendas(self, origem: Path):
        df, relatorio = ingest_legado(origem / "legado")
        assert len(relatorio["ingeridos"]) == 1
        assert relatorio["ingeridos"][0]["arquivo"] == "vendas_analitico.rel"
        assert not df.empty

    def test_declara_o_motivo_de_cada_arquivo_ignorado(self, origem: Path):
        _, relatorio = ingest_legado(origem / "legado")
        motivos = {i["arquivo"]: i["motivo"] for i in relatorio["ignorados"]}
        assert "agregado" in motivos["vendas_sintetico.rel"]
        assert "compra" in motivos["compras_analitico.rel"]

    def test_compra_nao_entra_como_faturamento(self, origem: Path):
        """Somar entradas ao faturamento inflaria a receita."""
        df, _ = ingest_legado(origem / "legado")
        assert (df["tipo_documento"] == "CI-Compra").sum() == 0

    def test_diretorio_inexistente_nao_quebra(self, tmp_path: Path):
        df, relatorio = ingest_legado(tmp_path / "nao_existe")
        assert df.empty
        assert relatorio["ingeridos"] == []

    def test_periodo_do_legado_vem_do_cabecalho(self, origem: Path):
        df, _ = ingest_legado(origem / "legado")

        assert set(df["periodo_inicio"]) == {date(2002, 1, 1)}
        assert set(df["periodo_fim"]) == {date(2022, 12, 31)}
        assert set(df["confianca_metadados"]) == {"DECLARADA"}


class TestHistoricoUnificado:
    """O pipeline publica os dois sistemas na mesma base."""

    def _executar(self, origem: Path):
        return run_pipeline(
            data_dir=origem / "raw",
            output_dir=origem / "processed",
            legado_dir=origem / "legado",
        )

    def test_base_contem_os_dois_sistemas(self, origem: Path):
        df = self._executar(origem)["dados"]
        assert set(df["sistema_origem"]) == {"ATUAL", "LEGADO"}

    def test_historico_atravessa_a_troca_de_sistema(self, origem: Path):
        """Do primeiro ano do legado ao último do sistema atual."""
        df = self._executar(origem)["dados"]
        anos = df["data_emissao"].dropna().map(lambda d: d.year)
        assert anos.min() == 2002
        assert anos.max() >= 2025
        assert anos.max() - anos.min() + 1 >= 24

    def test_procedencia_da_data_e_declarada(self, origem: Path):
        """Data lida e data inferida não se confundem na base publicada."""
        df = self._executar(origem)["dados"]
        atual = df[df["sistema_origem"] == "ATUAL"]["confianca_data"]
        legado = df[df["sistema_origem"] == "LEGADO"]["confianca_data"]
        assert set(atual) <= {"Registrada", "Ausente"}
        assert set(legado) <= {"Inferida", "Inferida (suspeita)"}

    def test_relatorio_da_execucao_lista_o_legado(self, origem: Path):
        resultado = self._executar(origem)
        assert resultado["etapas"]["ingestao_legado"]["linhas"] > 0
        assert resultado["etapas"]["ingestao_legado"]["ignorados"] == 2

    def test_legado_e_opcional(self, origem: Path):
        """Sem o diretório do legado, publica só o histórico atual."""
        resultado = run_pipeline(
            data_dir=origem / "raw",
            output_dir=origem / "processed",
            legado_dir=None,
        )
        assert set(resultado["dados"]["sistema_origem"]) == {"ATUAL"}

    def test_chaves_dos_dois_sistemas_nao_colidem(self, origem: Path):
        df = self._executar(origem)["dados"]
        assert df["id_item_venda"].is_unique

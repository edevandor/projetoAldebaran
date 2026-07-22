"""Testes de integração dos parsers do ERP legado (.rel, 2002–2022).

Os arquivos reais são confidenciais. Estes testes usam os geradores
sintéticos, que reproduzem o mesmo layout de 132 colunas e as mesmas
anomalias de datação — é isso que torna o tratamento do legado
verificável por quem não tem acesso aos dados originais.
"""

from pathlib import Path

import pytest

from demo.gerador_rel import (
    LARGURA,
    SENTINELA_DATA,
    gerar_rel_analitico,
    gerar_rel_analitico_com_gabarito,
    gerar_rel_compras,
    gerar_rel_sintetico,
)
from ingestion.parser_rel import parse_rel, parse_rel_to_df
from ingestion.parser_rel_analitico import parse_rel_analitico, parse_rel_analitico_to_df
from ingestion.parser_rel_compras import parse_rel_compras, parse_rel_compras_to_df
from ingestion.rel_comum import extrair_periodo


@pytest.fixture
def rel_sintetico(tmp_path: Path) -> Path:
    return gerar_rel_sintetico(tmp_path / "vendas_sintetico.rel", num_itens=60)


@pytest.fixture
def rel_analitico(tmp_path: Path) -> Path:
    return gerar_rel_analitico(tmp_path / "vendas_analitico.rel", num_vendas=120)


@pytest.fixture
def rel_compras(tmp_path: Path) -> Path:
    return gerar_rel_compras(tmp_path / "compras.rel", num_entradas=90)


class TestFormatoGerado:
    """O sintético só serve se reproduzir o layout do relatório de origem."""

    def test_todas_as_linhas_tem_largura_fixa(self, rel_analitico: Path):
        larguras = {
            len(linha)
            for linha in rel_analitico.read_text(encoding="latin-1").splitlines()
        }
        assert larguras == {LARGURA}

    def test_arquivo_em_latin1(self, rel_sintetico: Path):
        """O ERP legado exportava em latin-1, não UTF-8."""
        assert rel_sintetico.read_text(encoding="latin-1")

    def test_cabecalhos_de_pagina_repetidos(self, rel_analitico: Path):
        conteudo = rel_analitico.read_text(encoding="latin-1")
        assert conteudo.count("01-EMPRESA") > 1


class TestRelSintetico:
    """Relatório agregado: totais por item, sem venda individual."""

    def test_extrai_itens(self, rel_sintetico: Path):
        assert len(parse_rel(rel_sintetico)) == 60

    def test_ignora_cabecalhos_e_totais(self, rel_sintetico: Path):
        for registro in parse_rel(rel_sintetico):
            assert registro["codigo_item"].isdigit()
            assert not registro["descricao"].startswith("Total")

    def test_converte_numeros_brasileiros(self, rel_sintetico: Path):
        registros = parse_rel(rel_sintetico)
        assert all(isinstance(r["valor_total_venda"], float) for r in registros)
        assert any(r["valor_total_venda"] > 1000 for r in registros)

    def test_margem_percentual_extraida(self, rel_sintetico: Path):
        assert all(0 <= r["margem_pct"] <= 100 for r in parse_rel(rel_sintetico))

    def test_df_declara_ausencia_de_data(self, rel_sintetico: Path):
        """O agregado não tem data — a coluna existe vazia, não é inventada."""
        df = parse_rel_to_df(rel_sintetico)
        assert df["data_emissao"].isna().all()


class TestRelAnalitico:
    """Relatório analítico: uma linha por item de venda, ano com 2 dígitos."""

    def test_extrai_vendas(self, rel_analitico: Path):
        assert len(parse_rel_analitico(rel_analitico)) > 100

    def test_reconstroi_as_duas_decadas(self, rel_analitico: Path):
        """O ano de 2 dígitos é desambiguado pela sequência de CI."""
        anos = {r["data_emissao"].year for r in parse_rel_analitico(rel_analitico)}
        assert min(anos) == 2002
        assert max(anos) == 2022
        assert len(anos) >= 20

    def test_reconstroi_o_ano_real_de_cada_venda(self, tmp_path: Path):
        """Compara a reconstrução com o ano em que a venda de fato ocorreu.

        Verificar apenas que o ano nunca decresce não provaria nada: o
        algoritmo garante isso por construção, e passaria até sobre uma
        série inteiramente errada. O gerador devolve o gabarito {ci: ano}
        justamente para que este teste possa falhar.
        """
        caminho, gabarito = gerar_rel_analitico_com_gabarito(
            tmp_path / "com_gabarito.rel", num_vendas=120
        )
        registros = parse_rel_analitico(caminho)

        divergencias = [
            (r["ci"], gabarito[r["ci"]], r["data_emissao"].year)
            for r in registros
            if gabarito[r["ci"]] != r["data_emissao"].year
        ]
        assert not divergencias, f"anos reconstruídos errados: {divergencias[:5]}"

    def test_ano_corrompido_nao_contamina_a_serie(self, tmp_path: Path):
        """Um ano impresso fora do período não pode arrastar o resto.

        A reconstrução impede o ano de retroceder. Sem validação contra o
        período do relatório, um único '99' no meio do arquivo empurrava
        todos os registros seguintes para 2099.
        """
        caminho, gabarito = gerar_rel_analitico_com_gabarito(
            tmp_path / "corrompido.rel", num_vendas=120
        )
        linhas = caminho.read_text(encoding="latin-1").splitlines()
        alvo = next(
            i for i, linha in enumerate(linhas)
            if linha[92:102].strip().endswith("/09")
        )
        corrompida = linhas[alvo]
        linhas[alvo] = (
            corrompida[:92] + f"{corrompida[92:100]}99".rjust(10) + corrompida[102:]
        )
        caminho.write_text("\n".join(linhas) + "\n", encoding="latin-1")

        registros = parse_rel_analitico(caminho)
        anos = [r["data_emissao"].year for r in registros]

        assert max(anos) <= 2022, "o ano corrompido vazou para a série"
        assert sum(1 for r in registros if r["ano_suspeito"]) == 1
        corretos = sum(1 for r in registros if gabarito[r["ci"]] == r["data_emissao"].year)
        assert corretos >= len(registros) - 1

    def test_uma_venda_agrupa_varios_itens(self, rel_analitico: Path):
        """Granularidade do relatório é o item: o mesmo CI repete-se."""
        registros = parse_rel_analitico(rel_analitico)
        cis = [r["ci"] for r in registros]
        assert len(cis) > len(set(cis))

    def test_df_numera_itens_dentro_da_venda(self, rel_analitico: Path):
        df = parse_rel_analitico_to_df(rel_analitico)
        assert (df["tipo_documento"] == "CI").all()
        primeiro_ci = df["numero_documento"].iloc[0]
        protocolos = df[df["numero_documento"] == primeiro_ci]["protocolo"]
        assert len(protocolos) == protocolos.nunique()

    def test_identidade_do_item_resiste_a_reordenacao_global(self, rel_analitico: Path):
        original = parse_rel_analitico_to_df(rel_analitico)
        ci = original["numero_documento"].value_counts().index[0]
        esperado = set(
            original.loc[original["numero_documento"] == ci, ["produto", "protocolo"]]
            .itertuples(index=False, name=None)
        )

        linhas = rel_analitico.read_text(encoding="latin-1").splitlines()
        indices = [
            indice
            for indice, linha in enumerate(linhas)
            if len(linha) >= 116 and linha[102:116].strip() == ci
        ]
        invertidas = [linhas[indice] for indice in reversed(indices)]
        for indice, linha in zip(indices, invertidas, strict=True):
            linhas[indice] = linha
        rel_analitico.write_text("\n".join(linhas) + "\n", encoding="latin-1")

        reordenado = parse_rel_analitico_to_df(rel_analitico)
        obtido = set(
            reordenado.loc[reordenado["numero_documento"] == ci, ["produto", "protocolo"]]
            .itertuples(index=False, name=None)
        )

        assert obtido == esperado


class TestRelCompras:
    """Compras: datas corrompidas, reconstruídas a partir do CI."""

    def test_sentinela_presente_na_origem(self, rel_compras: Path):
        """O defeito que o parser existe para tratar tem de estar no arquivo."""
        assert SENTINELA_DATA in rel_compras.read_text(encoding="latin-1")

    def test_toda_entrada_recebe_data_reconstruida(self, rel_compras: Path):
        registros = parse_rel_compras(rel_compras)
        assert registros
        assert all(r["data_entrada"] is not None for r in registros)

    def test_ano_reconstruido_respeita_o_periodo_do_cabecalho(self, rel_compras: Path):
        """O período vem do cabeçalho do relatório, não de constante no código."""
        anos = {r["ano_inferido"] for r in parse_rel_compras(rel_compras)}
        assert extrair_periodo(rel_compras) == (2005, 2022)
        assert min(anos) >= 2005
        assert max(anos) <= 2022

    def test_periodo_declarado_muda_a_reconstrucao(self, tmp_path: Path):
        """Um relatório curto não pode ser espalhado por duas décadas."""
        caminho = gerar_rel_compras(tmp_path / "curto.rel", num_entradas=12)
        texto = caminho.read_text(encoding="latin-1").replace(
            "01/01/2005 a 31/12/2022", "01/01/2021 a 31/12/2022"
        )
        caminho.write_text(texto, encoding="latin-1")

        anos = {r["ano_inferido"] for r in parse_rel_compras(caminho)}
        assert anos <= {2021, 2022}

    def test_periodo_pode_ser_sobrescrito(self, rel_compras: Path):
        anos = {
            r["ano_inferido"]
            for r in parse_rel_compras(rel_compras, ano_inicial=2019, ano_final=2020)
        }
        assert anos <= {2019, 2020}

    def test_confianca_declarada_por_registo(self, rel_compras: Path):
        """A data reconstruída nunca é apresentada como certeza."""
        niveis = {r["confianca"] for r in parse_rel_compras(rel_compras)}
        assert niveis <= {"Alta", "Media", "Baixa", "Invalido"}
        assert "Baixa" in niveis  # há sentinelas no arquivo

    def test_data_original_preservada(self, rel_compras: Path):
        """A data impressa no relatório é mantida ao lado da reconstruída."""
        registros = parse_rel_compras(rel_compras)
        assert all(r["data_original"] for r in registros)
        assert any(r["data_original"] == SENTINELA_DATA for r in registros)

    def test_df_compativel_com_o_pipeline(self, rel_compras: Path):
        df = parse_rel_compras_to_df(rel_compras)
        for coluna in ("produto", "data_emissao", "numero_documento", "protocolo"):
            assert coluna in df.columns

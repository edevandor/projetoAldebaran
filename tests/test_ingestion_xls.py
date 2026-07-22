"""Testes do caminho .xls — a tabela plana exportada pelo ERP.

O formato .xls binário não tem escritor mantido em Python, então a leitura
do arquivo e a extração dos registros foram separadas: aqui se verifica a
extração, sobre linhas equivalentes às que o xlrd entrega.
"""

from datetime import date

import pytest

from ingestion.directory import extrair_registros_xls

CABECALHO = [
    ["EMPRESA DEMONSTRACAO LTDA", None, None, None, None, None, None, None],
    ["Data..:", 45000.0, None, None, None, None, None, None],
    ["CSD067.Mapa Est. de Vendas", None, None, None, None, None, None, None],
    ["Produto", "Estoque", None, None, None, "Und", "Qtde", "Data Emissao",
     "Protocolo", "NF No", None, None, None, "Total Venda"],
]


def _linha(produto="000101 - PRODUTO ALFA", data=45672.0, protocolo=334053.0,
           nf="001-100001", total=1500.5, qtd=2.0, und="UN"):
    return [produto, 50, None, None, None, und, qtd, data, protocolo, nf,
            None, None, None, total]


class TestExtracao:
    def test_extrai_linha_de_venda(self):
        registros = extrair_registros_xls([*CABECALHO, _linha()])
        assert len(registros) == 1
        assert registros[0]["produto"] == "000101 - PRODUTO ALFA"
        assert registros[0]["valor_total_venda"] == 1500.5

    def test_converte_serial_de_data_do_excel(self):
        registros = extrair_registros_xls([*CABECALHO, _linha(data=45672.0)])
        assert registros[0]["data_emissao"] == date(2025, 1, 15)

    def test_deriva_tipo_do_numero_do_documento(self):
        registros = extrair_registros_xls([*CABECALHO, _linha(nf="002-900001")])
        assert registros[0]["tipo_documento"] == "002"

    def test_protocolo_numerico_sem_notacao_decimal(self):
        registros = extrair_registros_xls([*CABECALHO, _linha(protocolo=334053.0)])
        assert registros[0]["protocolo"] == "334053"

    def test_valor_ausente_nao_e_inventado_como_zero(self):
        registros = extrair_registros_xls([*CABECALHO, _linha(total=None)])

        assert registros[0]["valor_total_venda"] is None


class TestLinhasQueNaoSaoDados:
    """Cabeçalhos e totais não podem entrar como se fossem venda."""

    @pytest.mark.parametrize("rotulo", [
        "Produto", "Total: Venda Direta", "Artigo: Venda Direta",
        "Responsavel: Carlos Silva", "Responsável: Carlos Silva", "",
    ])
    def test_rotulo_e_ignorado(self, rotulo):
        registros = extrair_registros_xls([[rotulo] + [None] * 13])
        assert registros == []

    def test_nao_depende_de_numero_fixo_de_linhas_de_cabecalho(self):
        """O cabeçalho varia entre exportações; pular contagem fixa perde venda."""
        curto = [CABECALHO[-1], _linha()]
        longo = [*CABECALHO, *CABECALHO, _linha()]
        assert len(extrair_registros_xls(curto)) == 1
        assert len(extrair_registros_xls(longo)) == 1


class TestDataAusente:
    """A regra de negócio: venda sem data é preservada, nunca descartada."""

    def test_linha_sem_data_e_preservada(self):
        registros = extrair_registros_xls([*CABECALHO, _linha(data=None)])
        assert len(registros) == 1
        assert registros[0]["data_emissao"] is None
        assert registros[0]["valor_total_venda"] == 1500.5

    def test_data_em_texto_nao_descarta_a_venda(self):
        registros = extrair_registros_xls([*CABECALHO, _linha(data="  ")])
        assert len(registros) == 1
        assert registros[0]["data_emissao"] is None

    def test_faturamento_nao_se_perde_quando_falta_data(self):
        linhas = [*CABECALHO, _linha(total=1000.0), _linha(data=None, total=500.0)]
        registros = extrair_registros_xls(linhas)
        assert sum(r["valor_total_venda"] for r in registros) == 1500.0

"""Geração do XLSX sintético no formato hierárquico do ERP atual.

Reproduz a estrutura de três níveis dos mapas estatísticos de vendas —
Responsável → Artigo → linhas de venda, com subtotais entre blocos —
que impede a leitura direta por `pd.read_excel`.
"""

import datetime
import random
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from demo.catalogo import ARTIGOS, PRODUTOS, RESPONSAVEIS, SEMENTE_PADRAO, UNIDADES

# Posições das colunas no relatório de origem (0-indexed).
COL_PRODUTO = 0   # A
COL_UND = 5       # F
COL_QTD = 6       # G
COL_DATA = 7      # H
COL_PROTOCOLO = 8  # I
COL_NF = 9        # J
COL_TOTAL = 13    # N

CABECALHOS = [
    "Produto", "Estoque", "", "", "", "Und", "Qtde", "Data Emissao",
    "Protocolo", "NF Nº", "", "", "", "Total Venda",
]


def gerar_xlsx(
    destino: Path,
    num_vendas: int = 50,
    seed: int = SEMENTE_PADRAO,
    data_inicial: datetime.date = datetime.date(2025, 1, 1),
) -> Path:
    """Gera um XLSX sintético com a estrutura hierárquica do ERP.

    Cada venda recebe de 1 a 3 itens, reproduzindo a granularidade real:
    a linha é o item da nota, não a nota.

    Args:
        destino: Caminho do arquivo a criar.
        num_vendas: Vendas por responsável, distribuídas entre os artigos.
        seed: Semente do gerador, para saídas reproduzíveis.
        data_inicial: Primeira data possível de emissão.

    Returns:
        Path do arquivo criado.
    """
    rng = random.Random(seed)
    destino = Path(destino)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MapaVendas"
    negrito = Font(bold=True)
    linha_atual = 1
    sequencia_nf = 0

    def _escrever(coluna: int, valor, bold: bool = False) -> None:
        celula = ws.cell(row=linha_atual, column=coluna + 1, value=valor)
        if bold:
            celula.font = negrito

    for responsavel in RESPONSAVEIS:
        vendas_por_artigo = max(1, num_vendas // len(ARTIGOS))

        for artigo in ARTIGOS:
            _escrever(COL_PRODUTO, f"Responsavel: {responsavel}", bold=True)
            linha_atual += 1
            _escrever(COL_PRODUTO, f"Artigo: {artigo}", bold=True)
            linha_atual += 1

            for indice, cabecalho in enumerate(CABECALHOS):
                _escrever(indice, cabecalho, bold=True)
            linha_atual += 1

            for _ in range(min(vendas_por_artigo, 20)):
                sequencia_nf += 1
                nf = f"001-{100000 + sequencia_nf:06d}"
                data = data_inicial + datetime.timedelta(days=rng.randint(0, 540))

                for item in range(rng.randint(1, 3)):
                    codigo, descricao = PRODUTOS[rng.randrange(len(PRODUTOS))]
                    qtd = round(rng.uniform(1, 12), 2)
                    total = round(qtd * rng.uniform(15, 800), 2)

                    _escrever(COL_PRODUTO, f"{codigo} - {descricao}")
                    _escrever(COL_UND, rng.choice(UNIDADES))
                    _escrever(COL_QTD, qtd)
                    _escrever(COL_DATA, data)
                    _escrever(COL_PROTOCOLO, f"{sequencia_nf:04d}{item + 1:02d}")
                    _escrever(COL_NF, nf)
                    _escrever(COL_TOTAL, total)
                    linha_atual += 1

            _escrever(COL_PRODUTO, f"Total: {artigo}", bold=True)
            linha_atual += 1

        _escrever(COL_PRODUTO, f"Total: Responsavel: {responsavel}", bold=True)
        linha_atual += 1

    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)
    return destino

"""Elementos compartilhados pelos parsers do ERP legado.

Os três relatórios `.rel` usam o mesmo dialeto: largura fixa de 132
colunas, codificação latin-1, números no padrão brasileiro e um cabeçalho
de página que se repete a cada bloco. Este módulo concentra o que é comum,
para que cada parser trate apenas o que é específico do seu layout.
"""

import re
from pathlib import Path

LARGURA_LINHA = 132
ENCODING = "latin-1"

RE_PERIODO = re.compile(
    r"Periodo:\s*\d{2}/\d{2}/(\d{4})\s+a\s+\d{2}/\d{2}/(\d{4})"
)

# Marcas de linha que não são dados: cabeçalho de página, separador e total.
PREFIXOS_IGNORADOS = ("=", "-", "01-EMPRESA", "Item  Artigo", "Item   Artigo", "    Total")
TRECHOS_IGNORADOS = (
    "SISTEMA",
    "Periodo:",
    "Mapa Estatistico",
    "Almox..:",
    "MODULO DE VENDAS",
    "MODULO DE COMPRAS",
    "Total Movto",
    "Tipo Movto",
)


def parse_br_num(valor: str) -> float | None:
    """Converte número no formato brasileiro (1.234,56) para float.

    Campo em branco significa zero no layout. Texto malformado permanece
    ausente para não inventar um valor monetário válido.
    """
    valor = valor.strip()
    if not valor:
        return 0.0
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    else:
        valor = valor.replace(".", "")
    try:
        return float(valor)
    except ValueError:
        return None


def parse_margem(valor: str) -> float | None:
    """Converte percentual ('64,29%' ou '64,29') para float."""
    return parse_br_num(valor.strip().rstrip("%"))


def parse_data_br(data_str: str) -> tuple[int, int, str] | None:
    """Parseia data `dd/mm/aa`, devolvendo (dia, mês, ano com 2 dígitos).

    Retorna None quando o campo está vazio ou malformado.
    """
    data_str = data_str.strip()
    if not data_str or len(data_str) < 8:
        return None
    partes = data_str.split("/")
    if len(partes) != 3:
        return None
    try:
        return int(partes[0]), int(partes[1]), partes[2]
    except ValueError:
        return None


def extrair_periodo(path: str | Path, max_linhas: int = 30) -> tuple[int, int] | None:
    """Lê no cabeçalho o período que o relatório cobre.

    O próprio arquivo declara o intervalo ("Periodo: 01/01/2005 a
    31/12/2022"). Usar essa informação evita fixar no código o período de
    um relatório específico.

    Returns:
        Tupla (ano_inicial, ano_final), ou None se não estiver declarado.
    """
    with open(path, encoding=ENCODING) as f:
        for _ in range(max_linhas):
            linha = f.readline()
            if not linha:
                break
            achado = RE_PERIODO.search(linha)
            if achado:
                inicio, fim = int(achado.group(1)), int(achado.group(2))
                if inicio <= fim:
                    return inicio, fim
    return None


def eh_linha_de_dados(linha: str) -> bool:
    """Indica se a linha carrega dados, e não moldura do relatório."""
    if len(linha) < LARGURA_LINHA or not linha.strip():
        return False
    if linha.startswith(PREFIXOS_IGNORADOS):
        return False
    return not any(trecho in linha for trecho in TRECHOS_IGNORADOS)

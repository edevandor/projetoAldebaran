"""Parser de ficheiro .rel — Mapa Estatístico de Vendas Sintético (2002-2022).

Formato legado de exportação do sistema ERP legado.
Ficheiro de texto com linhas de comprimento fixo (132 chars),
layout de página com cabeçalhos repetidos.

Não contém dados individuais de venda (data, NF, vendedor) — é um
resumo sintético: total de quantidade e valor por item no período.
"""

import re
from pathlib import Path
from typing import List

# --- Constantes de posições (0-indexed) ---
COL_ITEM = (0, 6)             # Código do item
COL_DESCRICAO = (6, 54)       # Descrição/Referência
COL_QTD_ESTOQUE = (54, 63)    # Quantidade em estoque
COL_UND = (63, 67)            # Unidade de medida
COL_QTDE = (67, 84)           # Quantidade vendida (inclui padding)
COL_TOTAL_CUSTO = (84, 97)    # Custo total
COL_TOTAL_COMPRA = (97, 110)  # Valor total de venda (Total Compra)
COL_TOTAL_LIQ = (110, 122)    # Valor líquido (12 chars — absorve overflow p/ margem)
COL_MARGEM = (122, 132)       # % Margem (10 chars — sem o dígito extravasado)


def _parse_br_num(valor: str) -> float:
    """Converte número no formato brasileiro (1.234,56) para float.

    Remove pontos de milhar, substitui vírgula decimal por ponto.
    Retorna 0.0 para valores vazios ou inválidos.
    """
    valor = valor.strip()
    if not valor:
        return 0.0
    # Remove pontos de milhar, mas preserva o ponto decimal
    # Se tiver vírgula, é separador decimal → troca por ponto
    # Se não tiver vírgula mas tiver ponto, pode ser milhar ou decimal
    if "," in valor:
        # Formato brasileiro: 1.234,56 ou 12,50
        valor = valor.replace(".", "")   # Remove pontos de milhar
        valor = valor.replace(",", ".")  # Vírgula vira ponto decimal
    else:
        # Pode ser número inteiro como "1" ou "0"
        valor = valor.replace(".", "")   # Remove qualquer ponto de milhar
    try:
        return float(valor)
    except ValueError:
        return 0.0


def _parse_margem(valor: str) -> float:
    """Converte percentual como '64,29%' ou '64,29' para float (ex: 64.29).

    Retorna 0.0 para valores vazios.
    """
    valor = valor.strip().rstrip("%")
    return _parse_br_num(valor)


def _parse_linha_dados(linha: str) -> dict | None:
    """Parseia uma linha de dados do .rel.

    Retorna dict com os campos extraídos, ou None se a linha
    não for uma linha de dados válida.
    """
    if len(linha) < 132:
        return None

    codigo_item = linha[COL_ITEM[0]:COL_ITEM[1]].strip()
    if not codigo_item.isdigit():
        return None

    descricao = linha[COL_DESCRICAO[0]:COL_DESCRICAO[1]].strip()
    if not descricao or descricao.startswith("-"):
        return None

    # Montar o campo produto (mesmo formato do XLSX para compatibilidade)
    produto = f"{codigo_item} - {descricao}"

    # Quantidade vendida — campo [67:84] = 17 chars
    qtde_raw = linha[COL_QTDE[0]:COL_QTDE[1]]
    qtde = _parse_br_num(qtde_raw)

    # Valor total de compra (venda)
    compra_raw = linha[COL_TOTAL_COMPRA[0]:COL_TOTAL_COMPRA[1]]
    valor_total = _parse_br_num(compra_raw)

    # Total líquido e % Margem — campo Total Liq. tem 12 chars para
    # absorver o dígito decimal que extravasa do layout de 132 chars
    total_liquido = _parse_br_num(linha[COL_TOTAL_LIQ[0]:COL_TOTAL_LIQ[1]])
    margem_pct = _parse_margem(linha[COL_MARGEM[0]:COL_MARGEM[1]])

    return {
        "codigo_item": codigo_item,
        "descricao": descricao,
        "produto": produto,
        "quantidade": qtde,
        "unidade_medida": linha[COL_UND[0]:COL_UND[1]].strip(),
        "qtd_estoque": _parse_br_num(linha[COL_QTD_ESTOQUE[0]:COL_QTD_ESTOQUE[1]]),
        "total_custo": _parse_br_num(linha[COL_TOTAL_CUSTO[0]:COL_TOTAL_CUSTO[1]]),
        "valor_total_venda": valor_total,
        "total_liquido": total_liquido,
        "margem_pct": margem_pct,
    }


def parse_rel(path: str | Path) -> List[dict]:
    """Parseia um ficheiro .rel de mapa estatístico de vendas sintético.

    Ignora cabeçalhos de página, separadores e linhas de total.
    Retorna lista de dicionários, um por item vendido.

    O resultado NÃO contém data_emissao, NF, protocolo nem vendedor —
    o .rel é um resumo sintético (quantidade + valor agregados por
    item no período 2002-2022). Usar 'sistema_origem = ANTIGO' para
    distinguir dos dados pós-2023.

    Args:
        path: Caminho do ficheiro .rel.

    Returns:
        Lista de dicionários com os dados dos itens.
    """
    resultados: List[dict] = []

    with open(path, "r", encoding="latin-1") as f:
        for linha in f:
            linha = linha.rstrip("\r\n")

            if not linha or len(linha) < 132:
                continue

            # Ignorar separadores
            if linha.startswith("=") or linha.startswith("-"):
                continue

            # Ignorar cabeçalhos de página
            if linha.startswith("01-EMPRESA"):
                continue
            if "MODULO DE VENDAS" in linha:
                continue
            if "SISTEMA" in linha or "Periodo:" in linha:
                continue
            if "Mapa Estatistico" in linha:
                continue
            if "Almox..:" in linha:
                continue

            # Ignorar cabeçalho de colunas
            if linha.startswith("Item  Artigo"):
                continue

            # Ignorar linhas de total
            if linha.startswith("    Total"):
                continue

            # Linhas em branco entre páginas
            if linha.strip() == "":
                continue

            # Linha de dados
            campos = _parse_linha_dados(linha)
            if campos is not None:
                resultados.append(campos)
    return resultados


def parse_rel_to_df(path: str | Path) -> "pd.DataFrame":
    """Parseia .rel e retorna DataFrame padronizado.

    Adiciona as colunas necessárias para compatibilidade com o pipeline:
      - data_emissao como None (não existe no .rel)
      - tipo_documento, numero_documento, protocolo como string vazia
      - arquivo_origem com o nome do ficheiro

    Args:
        path: Caminho do ficheiro .rel.

    Returns:
        DataFrame com dados padronizados.
    """
    import pandas as pd

    dados = parse_rel(path)
    if not dados:
        return pd.DataFrame()

    df = pd.DataFrame(dados)
    df["data_emissao"] = None
    df["tipo_documento"] = ""
    df["numero_documento"] = ""
    df["protocolo"] = ""
    df["arquivo_origem"] = Path(path).name
    return df

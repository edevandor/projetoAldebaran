"""Parser de ficheiro .rel — Mapa Estatístico de Vendas Analítico (2002-2022).

Formato legado do sistema ERP legado.
Ficheiro de texto com linhas de comprimento fixo (132 chars),
layout de página com cabeçalhos repetidos.

ESTRUTURA:
  - Cabeçalhos de página (ignorados)
  - Linhas de dados com: Item, Descricao, Qtd.Est., UND,
    Quantidade, Dt.Saida (dd/mm/aa), CI, Total Item
  - Sem linhas de continuação (descrição cabe em 60 chars)
  - Totais de movimento (ignorados)

DIFERENÇAS DO SINTÉTICO (.rel anterior):
  - Relatório ANALÍTICO (vendas individuais, não agregadas)
  - Tem Dt.Saida (data) e CI (identificador da venda)
  - CI substitui NF como identificador de venda
  - Ano na data tem 2 dígitos (dd/mm/aa) — desambiguado pelo CI
"""

import datetime
import re
from collections import defaultdict
from pathlib import Path
from typing import List

# --- Constantes de posições (0-indexed, linha de 132 chars) ---
COL_ITEM = (0, 6)             # Código do produto (6 dígitos)
COL_DESCRICAO = (6, 66)       # Descrição/Referência (60 chars)
COL_QTD_ESTOQUE = (66, 71)    # Quantidade em estoque
COL_UND = (71, 74)            # Unidade de medida
# padding: 74-80 (6 chars)
COL_QUANTIDADE = (80, 92)     # Quantidade vendida
COL_DATA = (92, 102)          # Data de saída (dd/mm/aa)
COL_CI = (102, 116)           # Controle Interno (identificador da venda)
COL_TOTAL = (116, 132)        # Total do item


def _parse_br_num(valor: str) -> float:
    """Converte número brasileiro (1.234,56) para float."""
    valor = valor.strip()
    if not valor:
        return 0.0
    if "," in valor:
        valor = valor.replace(".", "")
        valor = valor.replace(",", ".")
    else:
        valor = valor.replace(".", "")
    try:
        return float(valor)
    except ValueError:
        return 0.0


def _parse_data_br(data_str: str) -> tuple:
    """Parseia data dd/mm/aa, retorna (dia, mes, ano_2d) ou None."""
    data_str = data_str.strip()
    if not data_str or len(data_str) < 8:
        return None
    partes = data_str.split("/")
    if len(partes) != 3:
        return None
    try:
        dia, mes, aa = int(partes[0]), int(partes[1]), partes[2]
        return (dia, mes, aa)
    except ValueError:
        return None


def _desambiguar_anos(registros: List[dict]) -> List[dict]:
    """Corrige anos de 2 dígitos usando a sequência crescente de CI.

    O CI (Controle Interno) é um número sequencial que só cresce.
    Se o ano de 2 dígitos regredir mas o CI continuar a subir,
    o ano real deve ser o anterior (ou o seguinte, se for virada de ano).

    Algoritmo:
      1. Atribuir ano_candidato = 2000 + int(aa)
      2. Ordenar por CI ascendente
      3. Percorrer: se ano_candidato < ano_anterior, usar ano_anterior
         (corrige regressões causadas por datas no fim/começo do ano)
    """
    if not registros:
        return registros

    # Ordenar por CI
    sorted_reg = sorted(registros, key=lambda r: r["_ci_num"])

    # Forward-fill de anos
    ano_anterior: int | None = None
    for r in sorted_reg:
        ano_cand = r["_ano_cand"]
        if ano_anterior is not None and ano_cand < ano_anterior:
            ano_cand = ano_anterior
        # Se ano_cand > ano_anterior + 1, mantém o candidato
        # (pode ser virada de ano legítima)
        r["ano_real"] = ano_cand
        ano_anterior = ano_cand

    # Reordenar por CI para devolver (mesma ordem original seria perdida,
    # mas como é tudo dict, o processing a montante não depende de ordem)
    return sorted_reg


def _extrair_ano_ci(registros: List[dict]) -> List[dict]:
    """Extrai CI e ano candidato de cada registro.

    Adiciona campos internos _ci_num e _ano_cand para desambiguação.
    """
    for r in registros:
        r["_ci_num"] = r.pop("_ci_raw")
        r["_ano_cand"] = r.pop("_ano_raw")
    return registros


def parse_rel_analitico(path: str | Path) -> List[dict]:
    """Parseia ficheiro .rel analítico com vendas individuais.

    Ignora cabeçalhos de página, separadores, totais de movimento.
    Desambigua anos de 2 dígitos usando a sequência de CI.

    Retorna lista de dicionários, um por item vendido.

    Args:
        path: Caminho do ficheiro .rel.

    Returns:
        Lista de dicts com: codigo_item, descricao, quantidade,
        unidade_medida, data_emissao (datetime.date), ci,
        valor_total_venda, qtd_estoque.
    """
    registros: List[dict] = []

    with open(path, "r", encoding="latin-1") as f:
        for linha in f:
            linha = linha.rstrip("\r\n")

            # Pular linhas curtas
            if len(linha) < 132:
                continue

            # Pular separadores
            if linha.startswith("=") or linha.startswith("-"):
                continue

            # Pular cabeçalhos de página
            if (linha.startswith("01-EMPRESA")
                    or "SISTEMA" in linha
                    or "Periodo:" in linha
                    or "Mapa Estatistico" in linha
                or "Almox..:" in linha):
                continue

            # Pular cabeçalho de colunas
            if linha.startswith("Item  Artigo"):
                continue

            # Pular linhas de total
            if linha.startswith("    Total") or "Total Movto" in linha:
                continue

            # Pular linhas de tipo de movimento
            if "Tipo Movto" in linha:
                continue

            # Pular linhas em branco
            if linha.strip() == "":
                continue

            # Linha de dados — começa com 6 dígitos
            codigo_raw = linha[COL_ITEM[0]:COL_ITEM[1]]
            if not codigo_raw.strip().isdigit():
                continue

            codigo_item = codigo_raw.strip()

            # Descrição
            descricao = linha[COL_DESCRICAO[0]:COL_DESCRICAO[1]].strip()
            if not descricao:
                continue

            # Data
            data_parsed = _parse_data_br(linha[COL_DATA[0]:COL_DATA[1]])
            if data_parsed is None:
                continue
            dia, mes, aa_str = data_parsed

            # CI
            ci_str = linha[COL_CI[0]:COL_CI[1]].strip()
            if not ci_str.isdigit():
                continue
            ci_num = int(ci_str)

            # Valor
            valor = _parse_br_num(linha[COL_TOTAL[0]:COL_TOTAL[1]])
            quantidade = _parse_br_num(linha[COL_QUANTIDADE[0]:COL_QUANTIDADE[1]])

            registros.append({
                "codigo_item": codigo_item,
                "descricao": descricao,
                "quantidade": quantidade,
                "unidade_medida": linha[COL_UND[0]:COL_UND[1]].strip(),
                "qtd_estoque": _parse_br_num(
                    linha[COL_QTD_ESTOQUE[0]:COL_QTD_ESTOQUE[1]]
                ),
                "valor_total_venda": valor,
                "_ci_raw": ci_num,
                "_ano_raw": 2000 + int(aa_str),
                "_dia_raw": dia,
                "_mes_raw": mes,
            })

    # Desambiguar anos pelo CI
    registros = _extrair_ano_ci(registros)
    registros = _desambiguar_anos(registros)

    # Montar resultado final com data resolvida
    resultado: List[dict] = []
    for r in registros:
        ano = r["ano_real"]
        mes = r["_mes_raw"]
        dia = r["_dia_raw"]
        try:
            data = datetime.date(ano, mes, dia)
        except ValueError:
            # Data inválida (ex: 31/02) — ignorar este registro
            continue

        resultado.append({
            "codigo_item": r["codigo_item"],
            "descricao": r["descricao"],
            "quantidade": r["quantidade"],
            "unidade_medida": r["unidade_medida"],
            "qtd_estoque": r["qtd_estoque"],
            "valor_total_venda": r["valor_total_venda"],
            "data_emissao": data,
            "ci": r["_ci_num"],
        })

    return resultado


def parse_rel_analitico_to_df(path: str | Path) -> "pd.DataFrame":
    """Parseia .rel analítico e retorna DataFrame padronizado.

    Adiciona colunas para compatibilidade com o pipeline:
      - produto = codigo_item + " - " + descricao
      - tipo_documento = "CI"
      - numero_documento = str(ci)
      - protocolo = sequência do item dentro do CI
      - id_venda = "CI-" + str(ci)
      - id_item_venda = id_venda + "-" + sequencia
      - arquivo_origem = nome do ficheiro
      - responsavel = "" (não existe no .rel)
      - artigo = "" (não existe no .rel)

    Args:
        path: Caminho do ficheiro .rel.

    Returns:
        DataFrame com dados padronizados.
    """
    import pandas as pd

    dados = parse_rel_analitico(path)
    if not dados:
        return pd.DataFrame()

    # Agrupar por CI para numerar sequência de itens
    ci_counts: dict = {}
    for r in dados:
        ci = r["ci"]
        ci_counts[ci] = ci_counts.get(ci, 0) + 1
        r["_seq"] = ci_counts[ci]

    df = pd.DataFrame(dados)

    df["produto"] = df["codigo_item"] + " - " + df["descricao"]
    df["tipo_documento"] = "CI"
    df["numero_documento"] = df["ci"].astype(str)
    df["protocolo"] = df["_seq"].astype(str)
    df["arquivo_origem"] = Path(path).name
    df["responsavel"] = ""
    df["artigo"] = ""

    df.drop(columns=["_seq"], inplace=True, errors="ignore")

    return df

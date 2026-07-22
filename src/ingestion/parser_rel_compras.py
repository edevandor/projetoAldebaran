"""Parser de arquivo .rel — Mapa Estatístico de Compras Analítico.

RECONSTRUÇÃO DE DATAS A PARTIR DO CI:
  A data impressa não é confiável: o ano aparece com 2 dígitos, boa parte
  dos registros traz a sentinela "01/01/19" no lugar da data real, e o ano
  impresso ("20") não acompanha o período coberto pelo relatório.

  O CI (Controle Interno) é sequencial e só cresce, então é o único eixo
  cronológico utilizável. A reconstrução funciona assim:

  1. agrupar os itens por CI e extrair a data modal de cada grupo;
  2. ler o período coberto no cabeçalho do relatório ("Periodo: ... a ...");
  3. distribuir os CIs linearmente dentro desse período, atribuindo a cada
     ano uma fatia proporcional do intervalo de CI;
  4. ancorar o último ciclo no ano final do período e caminhar para trás.

  Para CIs cuja data modal é a sentinela, o dia e o mês são descartados e
  apenas o ano inferido é aproveitado.

PREMISSA E LIMITE:
  O passo 3 assume que o volume de CIs por ano é aproximadamente constante
  ao longo do período. Em uma operação que cresceu ou encolheu muito, os
  anos intermediários saem deslocados. É uma estimativa, não uma medição —
  por isso cada registro carrega o nível de confiança e preserva a data
  originalmente impressa em `data_original`.
"""

import datetime
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from ingestion.rel_comum import (
    eh_linha_de_dados,
    extrair_periodo,
    parse_br_num,
    parse_data_br,
)

COL_ITEM = (0, 6)
COL_DESCRICAO = (6, 66)
COL_QTD_ESTOQUE = (66, 71)
COL_UND = (71, 74)
COL_QUANTIDADE = (80, 92)
COL_DATA = (92, 102)
COL_CI = (102, 116)
COL_TOTAL = (116, 132)

# Usados apenas quando o cabeçalho do relatório não declara o período.
ANO_FINAL_PADRAO = 2022
ANO_INICIAL_PADRAO = 2005
SENTINELA = "01/01/19"  # data padrão quando o sistema não tem a real
RE_PERIODO = re.compile(r"Periodo:\s*\d{2}/\d{2}/(\d{4})\s+a\s+\d{2}/\d{2}/(\d{4})")


def _agrupar_por_ci(itens: list[dict]) -> list[dict]:
    """Agrupa itens pelo mesmo CI, calcula data modal e metadados."""
    ci_groups: dict[int, dict] = {}
    for item in itens:
        ci = item["_ci"]
        if ci not in ci_groups:
            ci_groups[ci] = {
                "ci": ci,
                "datas_brutas": [],
                "itens": [],
                "almoxes": set(),
                "total_compra": 0.0,
                "itens_distintos": set(),
            }
        grp = ci_groups[ci]
        data_str = f"{item['_dia']:02d}/{item['_mes']:02d}/{item['_ano_2d']:02d}"
        grp["datas_brutas"].append(data_str)
        grp["itens"].append(item)
        grp["total_compra"] += item["_valor"]
        grp["itens_distintos"].add(item["codigo_item"])

    resultados = []
    for ci in sorted(ci_groups.keys()):
        grp = ci_groups[ci]
        # Moda das datas
        contagem = Counter(grp["datas_brutas"])
        data_modal, freq = contagem.most_common(1)[0]
        # Dia/mês mais comum
        dp = parse_data_br(data_modal)
        resultados.append({
            "ci": ci,
            "data_modal_str": data_modal,
            "freq_data": freq,
            "total_datas": len(grp["datas_brutas"]),
            "dia": dp[0] if dp else 1,
            "mes": dp[1] if dp else 1,
            "ano_2d": int(dp[2]) if dp else 20,
            "n_itens": len(grp["itens"]),
            "itens": grp["itens"],
            "total_compra": round(grp["total_compra"], 2),
            "itens_distintos": len(grp["itens_distintos"]),
            "almoxes": len(grp["almoxes"]),
        })
    return resultados


def _detectar_viradas(cis_agrupados: list[dict], n_anos: int) -> list[int]:
    """Marca onde cada ano começa, distribuindo os CIs linearmente.

    Cada ano do período recebe uma fatia proporcional do intervalo de CI.
    É uma estimativa: assume volume de CIs aproximadamente constante ao
    longo dos anos (ver a nota de premissa no topo do módulo).

    Args:
        cis_agrupados: Grupos de itens por CI, em ordem crescente de CI.
        n_anos: Quantidade de anos cobertos pelo relatório.
    """
    if not cis_agrupados or n_anos < 1:
        return []

    ci_min = cis_agrupados[0]["ci"]
    ci_max = cis_agrupados[-1]["ci"]
    range_total = ci_max - ci_min
    cis_por_ano = range_total / n_anos

    # Encontrar os índices onde a CI ultrapassa cada limite de ano
    transicoes = []
    for ano_offset in range(1, n_anos):
        ci_limite = ci_min + ano_offset * cis_por_ano
        # Encontrar o índice do primeiro CI >= ci_limite
        for idx, g in enumerate(cis_agrupados):
            if g["ci"] >= ci_limite:
                transicoes.append(idx)
                break

    return transicoes


def _inferir_anos(
    cis_agrupados: list[dict], transicoes: list[int], ano_final: int
) -> list[dict]:
    """Atribui anos a cada CI, ancorando o último ciclo em `ano_final`."""
    n = len(cis_agrupados)
    marcadores = [0] + transicoes + [n]
    num_ciclos = len(marcadores) - 1

    for idx in range(num_ciclos):
        inicio = marcadores[idx]
        fim = marcadores[idx + 1]
        ano = ano_final - (num_ciclos - 1 - idx)
        for j in range(inicio, fim):
            cis_agrupados[j]["ano_inferido"] = ano

    # CIs que ficaram sem ano (se houver, usar ano 0 e marcar como inválido)
    for g in cis_agrupados:
        if "ano_inferido" not in g:
            g["ano_inferido"] = 0
            g["confianca_ano"] = "Invalido"

    return cis_agrupados


def _atribuir_confianca(g: dict) -> str:
    """Nível de confiança para a data corrigida."""
    if g.get("ano_inferido", 0) == 0:
        return "Invalido"
    # Se a data modal é a sentinela → baixa confiança no dia/mês
    if g["data_modal_str"] == SENTINELA:
        return "Baixa"
    # Se tem poucos registros com esta data → média
    if g["freq_data"] < g["total_datas"] * 0.5:
        return "Media"
    # Se o ano impresso (2000 + aa) coincide com o inferido → alta
    ano_impresso = 2000 + g["ano_2d"]
    if ano_impresso == g["ano_inferido"]:
        return "Alta"
    # Se o mês/dia são coerentes com a vizinhança de CIs
    return "Media"


def parse_rel_compras(
    path: str | Path,
    ano_inicial: int | None = None,
    ano_final: int | None = None,
) -> list[dict]:
    """Parseia .rel de compras, reconstruindo as datas a partir do CI.

    O período coberto é lido do cabeçalho do relatório. Os argumentos
    permitem sobrescrevê-lo quando o cabeçalho estiver ausente ou errado.

    Args:
        path: Caminho do arquivo .rel.
        ano_inicial: Primeiro ano do período. Se None, lê do cabeçalho.
        ano_final: Último ano do período, usado como âncora. Se None, lê do
            cabeçalho.

    Returns:
        Lista de dicts com a data reconstruída, o nível de confiança e a
        data originalmente impressa.
    """
    if ano_inicial is None or ano_final is None:
        periodo = extrair_periodo(path)
        if periodo is not None:
            ano_inicial = ano_inicial if ano_inicial is not None else periodo[0]
            ano_final = ano_final if ano_final is not None else periodo[1]
    ano_inicial = ano_inicial if ano_inicial is not None else ANO_INICIAL_PADRAO
    ano_final = ano_final if ano_final is not None else ANO_FINAL_PADRAO
    n_anos = max(1, ano_final - ano_inicial + 1)

    # ─── 1a passada: extrair registros brutos ─────
    raw: list[dict] = []
    with open(path, encoding="latin-1") as f:
        for linha in f:
            linha = linha.rstrip("\r\n")
            if not eh_linha_de_dados(linha):
                continue

            codigo_raw = linha[COL_ITEM[0]:COL_ITEM[1]]
            if not codigo_raw.strip().isdigit():
                continue

            data_parsed = parse_data_br(linha[COL_DATA[0]:COL_DATA[1]])
            if data_parsed is None:
                continue
            dia, mes, ano_2d = data_parsed

            ci_str = linha[COL_CI[0]:COL_CI[1]].strip()
            if not ci_str.isdigit():
                continue

            raw.append({
                "codigo_item": codigo_raw.strip(),
                "descricao": linha[COL_DESCRICAO[0]:COL_DESCRICAO[1]].strip(),
                "quantidade": parse_br_num(linha[COL_QUANTIDADE[0]:COL_QUANTIDADE[1]]),
                "unidade_medida": linha[COL_UND[0]:COL_UND[1]].strip(),
                "qtd_estoque": parse_br_num(linha[COL_QTD_ESTOQUE[0]:COL_QTD_ESTOQUE[1]]),
                "_ci": int(ci_str),
                "_valor": parse_br_num(linha[COL_TOTAL[0]:COL_TOTAL[1]]),
                "_dia": dia,
                "_mes": mes,
                "_ano_2d": int(ano_2d),
            })

    # ─── 2a passada: agrupar por CI ─────
    cis_agrupados = _agrupar_por_ci(raw)

    # ─── 3a passada: detectar viradas ─────
    transicoes = _detectar_viradas(cis_agrupados, n_anos)

    # ─── 4a passada: atribuir anos ─────
    cis_agrupados = _inferir_anos(cis_agrupados, transicoes, ano_final)

    # ─── Expandir de volta para itens individuais ─────
    resultado = []
    for g in cis_agrupados:
        ano = g["ano_inferido"]
        conf = _atribuir_confianca(g)

        # Se ano é 0, pular
        if ano == 0:
            continue

        # Data corrigida
        dia = g["dia"] if g["data_modal_str"] != SENTINELA else 1
        mes = g["mes"] if g["data_modal_str"] != SENTINELA else 1
        try:
            data = datetime.date(ano, mes, dia)
        except ValueError:
            data = datetime.date(ano, 1, 1)

        for item in g["itens"]:
            resultado.append({
                "codigo_item": item["codigo_item"],
                "descricao": item["descricao"],
                "quantidade": item["quantidade"],
                "unidade_medida": item["unidade_medida"],
                "qtd_estoque": item["qtd_estoque"],
                "valor_total_compra": item["_valor"],
                "data_entrada": data,
                "ci": g["ci"],
                "ano_inferido": ano,
                "confianca": conf,
                "data_original": g["data_modal_str"],
            })

    return resultado


def parse_rel_compras_to_df(
    path: str | Path,
    ano_inicial: int | None = None,
    ano_final: int | None = None,
) -> pd.DataFrame:
    """Parseia .rel de compras e retorna DataFrame padronizado."""
    dados = parse_rel_compras(path, ano_inicial=ano_inicial, ano_final=ano_final)
    if not dados:
        return pd.DataFrame()

    ci_counts: dict = {}
    for r in dados:
        ci = r["ci"]
        ci_counts[ci] = ci_counts.get(ci, 0) + 1
        r["_seq"] = ci_counts[ci]

    df = pd.DataFrame(dados)

    df["produto"] = df["codigo_item"] + " - " + df["descricao"]
    df["tipo_documento"] = "CI-Compra"
    df["numero_documento"] = df["ci"].astype(str)
    df["protocolo"] = df["_seq"].astype(str)
    df["data_emissao"] = df["data_entrada"]
    df["valor_total_venda"] = df["valor_total_compra"]
    df["responsavel"] = ""
    df["artigo"] = ""
    df["arquivo_origem"] = Path(path).name

    df.drop(columns=["_seq", "data_entrada", "valor_total_compra"],
            inplace=True, errors="ignore")

    return df

"""Parser de ficheiro .rel — Mapa Estatístico de Compras Analítico.

CORRECAO DE DATAS POR CI:
  O CI é o único indicador cronológico fiável. O ano impresso ("20") está
  errado para a maioria dos registos. A correcção funciona em 3 passos:

  1. Agrupar itens por CI, extrair a moda das datas impressas em cada CI
  2. Ordenar CIs e detectar viradas de ano sustentadas: onde há uma
     transição Dez→Jan com CI a crescer E o volume de CIs antes/depois
     é significativo
  3. Ancorar o último ciclo em 2022, caminhar para trás

  Para CIs sem data modal confiável (ex: "01/01/19" sentinela), o
  dia/mês é descartado e só o ano inferido pelo CI é aproveitado.
"""

import datetime
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

COL_ITEM = (0, 6)
COL_DESCRICAO = (6, 66)
COL_QTD_ESTOQUE = (66, 71)
COL_UND = (71, 74)
COL_QUANTIDADE = (80, 92)
COL_DATA = (92, 102)
COL_CI = (102, 116)
COL_TOTAL = (116, 132)

ANO_ANCORA = 2022
MIN_CI_POR_CICLO = 30  # mínimo de CIs para considerar um ciclo válido
SENTINELA = "01/01/19"  # data padrão quando o sistema não tem a real


def _parse_br_num(valor: str) -> float:
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
        return 0.0


def _parse_data_br(data_str: str) -> Tuple[int, int, int] | None:
    data_str = data_str.strip()
    if not data_str or len(data_str) < 8:
        return None
    partes = data_str.split("/")
    if len(partes) != 3:
        return None
    try:
        return int(partes[0]), int(partes[1]), int(partes[2])
    except ValueError:
        return None


def _agrupar_por_ci(itens: List[dict]) -> List[dict]:
    """Agrupa itens pelo mesmo CI, calcula data modal e metadados."""
    ci_groups: Dict[int, dict] = {}
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
        dp = _parse_data_br(data_modal)
        resultados.append({
            "ci": ci,
            "data_modal_str": data_modal,
            "freq_data": freq,
            "total_datas": len(grp["datas_brutas"]),
            "dia": dp[0] if dp else 1,
            "mes": dp[1] if dp else 1,
            "ano_2d": dp[2] if dp else 20,
            "n_itens": len(grp["itens"]),
            "itens": grp["itens"],
            "total_compra": round(grp["total_compra"], 2),
            "itens_distintos": len(grp["itens_distintos"]),
            "almoxes": len(grp["almoxes"]),
        })
    return resultados


def _detectar_viradas(cis_agrupados: List[dict]) -> List[int]:
    """Detecta índices de virada de ano usando progressão linear de CI.

    Como as datas impressas são maioritariamente "20" (incorrectas),
    e o CI é o único indicador cronológico fiável, a melhor estimativa
    é uma interpolação linear do CI dentro do range total.

    O range CI vai de ~10005 a ~34064, cobrindo 18 anos (2005-2022).
    Cada ano recebe uma fatia proporcional do range de CI.
    """
    if not cis_agrupados:
        return []

    ci_min = cis_agrupados[0]["ci"]
    ci_max = cis_agrupados[-1]["ci"]
    range_total = ci_max - ci_min
    n_anos = 18  # 2005 a 2022
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


def _inferir_anos(cis_agrupados: List[dict], transicoes: List[int]) -> List[dict]:
    """Atribui anos a cada CI com base nas transições detectadas."""
    n = len(cis_agrupados)
    marcadores = [0] + transicoes + [n]
    num_ciclos = len(marcadores) - 1

    for idx in range(num_ciclos):
        inicio = marcadores[idx]
        fim = marcadores[idx + 1]
        ano = ANO_ANCORA - (num_ciclos - 1 - idx)
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
    # Se tem poucos registos com esta data → média
    if g["freq_data"] < g["total_datas"] * 0.5:
        return "Media"
    # Se o ano impresso (2000 + aa) coincide com o inferido → alta
    ano_impresso = 2000 + g["ano_2d"]
    if ano_impresso == g["ano_inferido"]:
        return "Alta"
    # Se o mês/dia são coerentes com a vizinhança de CIs
    return "Media"


def parse_rel_compras(path: str | Path) -> List[dict]:
    """Parseia .rel de compras com correção de datas por CI.

    Algoritmo:
      1. Extrair linhas brutas
      2. Agrupar por CI
      3. Detectar viradas de ano sustentadas (Dez→Jan)
      4. Atribuir anos por intervalo
      5. Montar resultado com data corrigida e confiança
    """
    # ─── 1a passada: extrair registros brutos ─────
    raw: List[dict] = []
    with open(path, "r", encoding="latin-1") as f:
        for linha in f:
            linha = linha.rstrip("\r\n")
            if len(linha) < 132:
                continue
            if (linha.startswith("=") or linha.startswith("-")
                or linha.startswith("01-EMPRESA")
                or "MODULO DE COMPRAS" in linha
                or "SISTEMA" in linha or "Periodo:" in linha
                or "Mapa Estatistico" in linha
                or "Almox..:" in linha
                or linha.startswith("Item   Artigo")
                or linha.startswith("    Total") or "Total Movto" in linha
                or "Tipo Movto" in linha
                or linha.strip() == ""):
                continue

            codigo_raw = linha[COL_ITEM[0]:COL_ITEM[1]]
            if not codigo_raw.strip().isdigit():
                continue

            data_parsed = _parse_data_br(linha[COL_DATA[0]:COL_DATA[1]])
            if data_parsed is None:
                continue
            dia, mes, ano_2d = data_parsed

            ci_str = linha[COL_CI[0]:COL_CI[1]].strip()
            if not ci_str.isdigit():
                continue

            raw.append({
                "codigo_item": codigo_raw.strip(),
                "descricao": linha[COL_DESCRICAO[0]:COL_DESCRICAO[1]].strip(),
                "quantidade": _parse_br_num(linha[COL_QUANTIDADE[0]:COL_QUANTIDADE[1]]),
                "unidade_medida": linha[COL_UND[0]:COL_UND[1]].strip(),
                "qtd_estoque": _parse_br_num(linha[COL_QTD_ESTOQUE[0]:COL_QTD_ESTOQUE[1]]),
                "_ci": int(ci_str),
                "_valor": _parse_br_num(linha[COL_TOTAL[0]:COL_TOTAL[1]]),
                "_dia": dia,
                "_mes": mes,
                "_ano_2d": ano_2d,
            })

    # ─── 2a passada: agrupar por CI ─────
    cis_agrupados = _agrupar_por_ci(raw)

    # ─── 3a passada: detectar viradas ─────
    transicoes = _detectar_viradas(cis_agrupados)

    # ─── 4a passada: atribuir anos ─────
    cis_agrupados = _inferir_anos(cis_agrupados, transicoes)

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


def parse_rel_compras_to_df(path: str | Path) -> "pd.DataFrame":
    """Parseia .rel de compras e retorna DataFrame padronizado."""
    import pandas as pd

    dados = parse_rel_compras(path)
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

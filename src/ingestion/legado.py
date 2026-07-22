"""Ingestão dos relatórios do ERP legado para dentro do pipeline.

Os três relatórios `.rel` não são equivalentes, e só um deles pode alimentar
a base de vendas:

  - **vendas analítico** — uma linha por item de venda, com data e CI.
    É o que se integra ao histórico.
  - **vendas sintético** — totais acumulados por item, sem data nem
    documento. Não tem granularidade de venda: somá-lo ao histórico
    inventaria vendas que o relatório não descreve.
  - **compras analítico** — entradas, não saídas. Não é faturamento.

Este módulo reconhece cada tipo, ingere o que é compatível e declara o que
ficou de fora, com o motivo (ver DECISIONS.md, D-017).
"""

import datetime
from pathlib import Path

import pandas as pd

from ingestion.parser_rel_analitico import parse_rel_analitico_to_df
from ingestion.rel_comum import ENCODING, eh_linha_de_dados, extrair_periodo, parse_data_br

COL_DATA = (92, 102)
COL_CI = (102, 116)

VENDAS_ANALITICO = "vendas_analitico"
VENDAS_SINTETICO = "vendas_sintetico"
COMPRAS = "compras"
DESCONHECIDO = "desconhecido"

MOTIVO_NAO_INGERIDO = {
    VENDAS_SINTETICO: "relatório agregado, sem granularidade de venda",
    COMPRAS: "movimento de compra, não de venda",
    DESCONHECIDO: "layout não reconhecido",
}


def detectar_tipo(path: str | Path) -> str:
    """Identifica qual dos relatórios do legado é o arquivo.

    O módulo aparece no cabeçalho de página; a distinção entre o analítico
    e o sintético de vendas vem do layout: só o analítico traz data de
    saída e CI nas posições fixas da linha.
    """
    with open(path, encoding=ENCODING) as f:
        conteudo = f.read()

    linhas = conteudo.splitlines()
    if any("MODULO DE COMPRAS" in linha for linha in linhas):
        return COMPRAS

    tem_vendas = any("MODULO DE VENDAS" in linha for linha in linhas)

    for linha in linhas:
        if not eh_linha_de_dados(linha):
            continue
        if not linha[:6].strip().isdigit():
            continue
        tem_data = parse_data_br(linha[COL_DATA[0]:COL_DATA[1]]) is not None
        tem_ci = linha[COL_CI[0]:COL_CI[1]].strip().isdigit()
        if tem_data and tem_ci:
            return VENDAS_ANALITICO
        return VENDAS_SINTETICO if tem_vendas else DESCONHECIDO

    return VENDAS_SINTETICO if tem_vendas else DESCONHECIDO


def ingest_legado(dir_path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Lê os `.rel` de um diretório e devolve o que alimenta o histórico.

    Args:
        dir_path: Diretório com os arquivos `.rel`. Inexistente ou vazio
            devolve um DataFrame vazio — o legado é opcional.

    Returns:
        Tupla (df, relatorio). O relatório lista os arquivos ingeridos e os
        ignorados, cada um com o motivo.
    """
    dir_path = Path(dir_path)
    relatorio: dict = {"ingeridos": [], "ignorados": [], "linhas": 0}

    if not dir_path.is_dir():
        return pd.DataFrame(), relatorio

    quadros: list[pd.DataFrame] = []
    for arquivo in sorted(dir_path.glob("*.rel")):
        tipo = detectar_tipo(arquivo)

        if tipo != VENDAS_ANALITICO:
            relatorio["ignorados"].append({
                "arquivo": arquivo.name,
                "tipo": tipo,
                "motivo": MOTIVO_NAO_INGERIDO.get(tipo, MOTIVO_NAO_INGERIDO[DESCONHECIDO]),
            })
            continue

        df = parse_rel_analitico_to_df(arquivo)
        if df.empty:
            relatorio["ignorados"].append({
                "arquivo": arquivo.name,
                "tipo": tipo,
                "motivo": "nenhum registro extraído",
            })
            continue

        periodo = extrair_periodo(arquivo)
        if periodo is not None:
            df["periodo_inicio"] = datetime.date(periodo[0], 1, 1)
            df["periodo_fim"] = datetime.date(periodo[1], 12, 31)
            df["confianca_metadados"] = "DECLARADA"
        else:
            df["periodo_inicio"] = None
            df["periodo_fim"] = None
            df["confianca_metadados"] = "AUSENTE"

        quadros.append(df)
        relatorio["ingeridos"].append({"arquivo": arquivo.name, "linhas": len(df)})

    if not quadros:
        return pd.DataFrame(), relatorio

    consolidado = pd.concat(quadros, ignore_index=True)
    relatorio["linhas"] = len(consolidado)
    return consolidado, relatorio

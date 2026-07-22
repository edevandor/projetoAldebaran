"""Parser de arquivo .rel — Mapa Estatístico de Vendas Analítico (2002-2022).

Formato legado do sistema ERP legado.
Arquivo de texto com linhas de comprimento fixo (132 chars),
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
from pathlib import Path

import pandas as pd

from ingestion.rel_comum import (
    eh_linha_de_dados,
    extrair_periodo,
    parse_br_num,
    parse_data_br,
)

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


def _desambiguar_anos(
    registros: list[dict],
    periodo: tuple[int, int] | None = None,
) -> list[dict]:
    """Reconstrói o ano de cada registro usando a sequência de CI.

    O CI é sequencial e só cresce, então ordená-lo ordena o tempo. O ano
    impresso tem 2 dígitos e regride ciclicamente ao longo do período; o
    algoritmo percorre os registros em ordem de CI e impede o retrocesso.

    Um ano impresso corrompido é o risco desse método: sem proteção, um
    único valor alto contamina todos os registros seguintes, porque a
    série nunca desce. Quando o relatório declara o período que cobre, o
    ano candidato é validado contra esse intervalo; o que estiver fora é
    descartado em favor do último ano válido, contendo o erro no registro
    em que ele ocorre (ver DECISIONS.md, D-016).

    Args:
        registros: Registros com `_ci_num` e `_ano_cand`.
        periodo: Intervalo (ano_inicial, ano_final) declarado no cabeçalho.
            Sem ele, não há como distinguir salto legítimo de corrupção.

    Returns:
        Os registros ordenados por CI, cada um com `ano_real` e
        `ano_suspeito` indicando se o valor impresso foi rejeitado.
    """
    if not registros:
        return registros

    sorted_reg = sorted(registros, key=lambda r: r["_ci_num"])

    ano_anterior: int | None = None
    for r in sorted_reg:
        ano_cand = r["_ano_cand"]
        fora_do_periodo = periodo is not None and not (periodo[0] <= ano_cand <= periodo[1])

        if fora_do_periodo:
            # O ano impresso não pode estar certo: o relatório não cobre
            # esse ano. Mantém o último válido em vez de arrastar a série.
            r["ano_suspeito"] = True
            ano_cand = ano_anterior if ano_anterior is not None else periodo[0]
        else:
            r["ano_suspeito"] = False
            if ano_anterior is not None and ano_cand < ano_anterior:
                ano_cand = ano_anterior

        r["ano_real"] = ano_cand
        ano_anterior = ano_cand

    return sorted_reg


def _extrair_ano_ci(registros: list[dict]) -> list[dict]:
    """Extrai CI e ano candidato de cada registro.

    Adiciona campos internos _ci_num e _ano_cand para desambiguação.
    """
    for r in registros:
        r["_ci_num"] = r.pop("_ci_raw")
        r["_ano_cand"] = r.pop("_ano_raw")
    return registros


def parse_rel_analitico(path: str | Path) -> list[dict]:
    """Parseia arquivo .rel analítico com vendas individuais.

    Ignora cabeçalhos de página, separadores, totais de movimento.
    Desambigua anos de 2 dígitos usando a sequência de CI.

    Retorna lista de dicionários, um por item vendido.

    Args:
        path: Caminho do arquivo .rel.

    Returns:
        Lista de dicts com: codigo_item, descricao, quantidade,
        unidade_medida, data_emissao (datetime.date), ci,
        valor_total_venda, qtd_estoque.
    """
    registros: list[dict] = []

    with open(path, encoding="latin-1") as f:
        for linha in f:
            linha = linha.rstrip("\r\n")

            if not eh_linha_de_dados(linha):
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
            data_parsed = parse_data_br(linha[COL_DATA[0]:COL_DATA[1]])
            if data_parsed is None:
                continue
            dia, mes, aa_str = data_parsed

            # CI
            ci_str = linha[COL_CI[0]:COL_CI[1]].strip()
            if not ci_str.isdigit():
                continue
            ci_num = int(ci_str)

            # Valor
            valor = parse_br_num(linha[COL_TOTAL[0]:COL_TOTAL[1]])
            quantidade = parse_br_num(linha[COL_QUANTIDADE[0]:COL_QUANTIDADE[1]])

            registros.append({
                "codigo_item": codigo_item,
                "descricao": descricao,
                "quantidade": quantidade,
                "unidade_medida": linha[COL_UND[0]:COL_UND[1]].strip(),
                "qtd_estoque": parse_br_num(
                    linha[COL_QTD_ESTOQUE[0]:COL_QTD_ESTOQUE[1]]
                ),
                "valor_total_venda": valor,
                "_ci_raw": ci_num,
                "_ano_raw": 2000 + int(aa_str),
                "_dia_raw": dia,
                "_mes_raw": mes,
            })

    # Desambiguar anos pelo CI, validando contra o período do cabeçalho
    registros = _extrair_ano_ci(registros)
    registros = _desambiguar_anos(registros, periodo=extrair_periodo(path))

    # Montar resultado final com data resolvida
    resultado: list[dict] = []
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
            "ano_suspeito": r.get("ano_suspeito", False),
        })

    return resultado


def parse_rel_analitico_to_df(path: str | Path) -> pd.DataFrame:
    """Parseia .rel analítico e retorna DataFrame padronizado.

    Adiciona colunas para compatibilidade com o pipeline:
      - produto = codigo_item + " - " + descricao
      - tipo_documento = "CI"
      - numero_documento = str(ci)
      - protocolo = sequência do item dentro do CI
      - id_venda = "CI-" + str(ci)
      - id_item_venda = id_venda + "-" + sequencia
      - arquivo_origem = nome do arquivo
      - responsavel = "" (não existe no .rel)
      - artigo = "" (não existe no .rel)

    Args:
        path: Caminho do arquivo .rel.

    Returns:
        DataFrame com dados padronizados.
    """

    dados = parse_rel_analitico(path)
    if not dados:
        return pd.DataFrame()

    # A identidade do item combina produto e ocorrência desse produto dentro
    # do CI. Assim, reordenar produtos diferentes no relatório não muda a
    # chave do item na próxima exportação.
    ci_counts: dict[tuple[int, str], int] = {}
    for r in dados:
        chave = (r["ci"], r["codigo_item"])
        ci_counts[chave] = ci_counts.get(chave, 0) + 1
        r["_seq"] = f"{r['codigo_item']}:{ci_counts[chave]}"

    df = pd.DataFrame(dados)

    df["produto"] = df["codigo_item"] + " - " + df["descricao"]
    # A data do legado é reconstruída a partir do CI, nunca lida direto.
    df["sistema_origem"] = "LEGADO"
    df["confianca_data"] = df["ano_suspeito"].map(
        {True: "Inferida (suspeita)", False: "Inferida"}
    )
    df["tipo_documento"] = "CI"
    df["numero_documento"] = df["ci"].astype(str)
    df["protocolo"] = df["_seq"].astype(str)
    df["arquivo_origem"] = Path(path).name
    df["responsavel"] = ""
    df["artigo"] = ""

    df.drop(columns=["_seq"], inplace=True, errors="ignore")

    return df

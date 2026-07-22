"""Padronização de dados de vendas.

Separa código e descrição do produto e gera as chaves de negócio
`id_venda` e `id_item_venda` com separador explícito.
"""

import datetime
from hashlib import sha256

import pandas as pd

from transformation.money import to_centavos

SEPARADOR_CHAVE = "|"
SEPARADOR_COLISAO = "#"
SEM_DATA = "SEM_DATA"


def _to_centavos_or_na(valor: object) -> object:
    """Converte dinheiro; mantém falhas observáveis para a quarentena."""
    if valor is None or pd.isna(valor):
        return pd.NA
    try:
        return to_centavos(valor)
    except (TypeError, ValueError):
        return pd.NA


def _split_produto(produto: object) -> tuple[str, str]:
    texto = "" if pd.isna(produto) else str(produto)
    if " - " not in texto:
        return "", texto
    codigo, descricao = texto.split(" - ", 1)
    return codigo, descricao


def _data_para_chave(valor: object) -> str:
    """Componente de data da chave, em ISO.

    Datas ausentes viram `SEM_DATA` em vez de 'None'/'NaT': o registro
    continua rastreável e a ausência fica explícita na própria chave.
    """
    if valor is None or pd.isna(valor):
        return SEM_DATA
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def _desambiguar_colisoes(
    chaves: pd.Series,
    sem_data: pd.Series,
    fontes: pd.Series,
) -> tuple[pd.Series, int, pd.Series]:
    """Torna únicas as chaves que colidem **por falta de data**.

    Sem data, dois documentos de mesmo número e mesmo protocolo produzem a
    mesma chave — o que faria duas vendas distintas colapsarem numa só
    identidade, violando a chave primária do dataset. Cada ocorrência
    recebe um sufixo ordinal estável (`#2`, `#3`, ...), preservando as duas
    vendas em vez de descartar uma delas em silêncio.

    A desambiguação se restringe às linhas sem data. Quando há data, a
    chave é confiável e uma colisão significa outra coisa: o mesmo item
    exportado em dois relatórios. Esse caso é de versão, não de
    identidade, e cabe a `resolve_versoes` — desambiguar aqui esconderia a
    dupla contagem de faturamento.

    Ver DECISIONS.md, D-015.
    """
    if not sem_data.any():
        return chaves, 0, pd.Series(False, index=chaves.index)

    candidatas = pd.DataFrame({
        "chave": chaves.where(sem_data),
        "fonte": fontes,
    })
    ocorrencia = candidatas.groupby(["chave", "fonte"], dropna=False).cumcount()
    ambiguas = sem_data & chaves.duplicated(keep=False)
    colide = ambiguas & (ocorrencia > 0)
    if not colide.any():
        return chaves, 0, ambiguas

    sufixo = pd.Series("", index=chaves.index)
    sufixo[colide] = ocorrencia[colide].map(lambda n: f"{SEPARADOR_COLISAO}{n + 1}")
    return chaves + sufixo, int(colide.sum()), ambiguas


def _token_produto(valor: object) -> str:
    normalizado = "" if pd.isna(valor) else " ".join(str(valor).casefold().split())
    return sha256(normalizado.encode("utf-8")).hexdigest()[:16]


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna uma cópia padronizada do DataFrame.

    Chaves geradas:
      - `id_venda` = numero_documento | data_emissao
      - `id_item_venda` = id_venda | protocolo

    `tipo_documento` não entra na chave por ser derivado do prefixo de
    `numero_documento` (ver DECISIONS.md, D-007).

    O total de colisões de chave resolvidas fica em
    `df.attrs["colisoes_chave"]`, para que o pipeline possa sinalizá-lo.
    """
    resultado = df.copy()
    split = resultado["produto"].apply(_split_produto)
    resultado["codigo_produto"] = split.str[0]
    resultado["descricao_produto"] = split.str[1]
    if "valor_total_venda_centavos" not in resultado.columns:
        resultado["valor_total_venda_centavos"] = resultado["valor_total_venda"].apply(
            _to_centavos_or_na
        )
    resultado["id_venda"] = (
        resultado["sistema_origem"].astype(str)
        + SEPARADOR_CHAVE
        + resultado["numero_documento"].astype(str)
        + SEPARADOR_CHAVE
        + resultado["data_emissao"].apply(_data_para_chave)
    )
    protocolo = resultado["protocolo"].fillna("").astype(str).str.strip()
    chaves = resultado["id_venda"] + SEPARADOR_CHAVE + protocolo
    protocolo_vazio = resultado["protocolo"].fillna("").astype(str).str.strip().eq("")
    resultado["confianca_identidade"] = "Observada"
    if protocolo_vazio.any():
        if "arquivo_origem" in resultado.columns:
            fonte = resultado["arquivo_origem"].astype(str)
        else:
            fonte = pd.Series("FONTE_UNICA", index=resultado.index)
        token = resultado["produto"].apply(_token_produto)
        ocorrencia = (
            pd.DataFrame({"fonte": fonte, "venda": resultado["id_venda"], "token": token})
            .groupby(["fonte", "venda", "token"], dropna=False)
            .cumcount()
            .add(1)
            .astype(str)
        )
        sufixo = "SEM_PROTOCOLO:" + token + ":" + ocorrencia
        chaves = chaves.mask(protocolo_vazio, chaves + sufixo)
        resultado.loc[protocolo_vazio, "confianca_identidade"] = (
            "Derivada (sem protocolo)"
        )
    sem_data = resultado["data_emissao"].isna()
    fontes = resultado.get(
        "arquivo_origem",
        pd.Series("FONTE_UNICA", index=resultado.index),
    ).astype(str)
    resultado["id_item_venda"], colisoes, ambiguas_sem_data = _desambiguar_colisoes(
        chaves,
        sem_data,
        fontes,
    )
    apenas_sem_data = ambiguas_sem_data & ~protocolo_vazio
    resultado.loc[apenas_sem_data, "confianca_identidade"] = "Derivada (sem data)"
    resultado.loc[ambiguas_sem_data & protocolo_vazio, "confianca_identidade"] = (
        "Derivada (sem data e protocolo)"
    )
    resultado.attrs["colisoes_chave"] = colisoes
    return resultado

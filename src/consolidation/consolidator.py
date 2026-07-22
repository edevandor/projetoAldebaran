"""Consolidação dos dados entre períodos e versões de relatório.

Duas operações distintas, aplicadas em momentos diferentes do pipeline:

  - `consolidate` remove linhas idênticas, exportadas mais de uma vez.
    Não depende das chaves de negócio, então roda antes da padronização.
  - `resolve_versoes` resolve o caso mais perigoso: o mesmo item de venda
    aparecendo em dois relatórios com conteúdo diferente — tipicamente um
    relatório parcial e a sua versão consolidada, com valor corrigido.
    Sem isso, o faturamento é contado duas vezes.
"""

import pandas as pd

CHAVE_ITEM = "id_item_venda"


def consolidate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove linhas duplicadas (todas as colunas iguais, exceto a origem).

    Mantém a primeira ocorrência. `arquivo_origem` e `linha_origem` ficam
    fora da comparação: a mesma venda exportada em dois arquivos é a mesma
    venda.

    Args:
        df: DataFrame de entrada.

    Returns:
        Tupla (df_sem_duplicatas, relatorio) com total_original,
        total_final e linhas_removidas.
    """
    ignoradas = {"arquivo_origem", "linha_origem"}
    cols_dedup = [c for c in df.columns if c not in ignoradas]
    total_original = len(df)

    if not cols_dedup or df.empty:
        return df.reset_index(drop=True), {
            "total_original": total_original,
            "total_final": total_original,
            "linhas_removidas": 0,
        }

    df_clean = df.drop_duplicates(subset=cols_dedup, keep="first")
    df_clean = df_clean.reset_index(drop=True)

    return df_clean, {
        "total_original": total_original,
        "total_final": len(df_clean),
        "linhas_removidas": total_original - len(df_clean),
    }


def resolve_versoes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Mantém uma única versão de cada item de venda.

    Quando o mesmo `id_item_venda` aparece em mais de um arquivo com
    conteúdo diferente, prevalece a ocorrência do arquivo que vem por
    último na ordem de ingestão — os arquivos são lidos em ordem
    alfabética, e a versão consolidada de um período é publicada depois
    da parcial.

    Esta é a regra que impede a dupla contagem de faturamento no
    reprocessamento de um período (ver DECISIONS.md, D-014).

    Args:
        df: DataFrame padronizado, com `id_item_venda`.

    Returns:
        Tupla (df_resolvido, relatorio) com os itens substituídos e os
        arquivos envolvidos.
    """
    if df.empty or CHAVE_ITEM not in df.columns:
        return df.reset_index(drop=True), {"versoes_substituidas": 0, "arquivos": []}

    duplicadas = df[CHAVE_ITEM].duplicated(keep=False)
    if not duplicadas.any():
        return df.reset_index(drop=True), {"versoes_substituidas": 0, "arquivos": []}

    conflitantes = df[duplicadas]
    arquivos = (
        sorted(conflitantes["arquivo_origem"].dropna().unique())
        if "arquivo_origem" in df.columns
        else []
    )

    candidato = df
    conflitos = pd.DataFrame(columns=df.columns)
    if "periodo_fim" in df.columns:
        candidato = df.assign(
            _periodo_fim_ordem=pd.to_datetime(df["periodo_fim"], errors="coerce")
        )
        indices_conflitantes: list[int] = []
        for _, grupo in candidato[duplicadas].groupby(CHAVE_ITEM, sort=False):
            periodo_maximo = grupo["_periodo_fim_ordem"].max()
            if bool(pd.isna(periodo_maximo)):
                continue
            finalistas = grupo.loc[grupo["_periodo_fim_ordem"] == periodo_maximo]
            if len(finalistas) > 1:
                # Se as versões mais recentes empatam, não há base segura para
                # escolher nem para ressuscitar uma versão antiga do item.
                indices_conflitantes.extend(list(grupo.index))

        if indices_conflitantes:
            conflitos = candidato.loc[indices_conflitantes].drop(
                columns=["_periodo_fim_ordem"], errors="ignore"
            )
            candidato = candidato.drop(index=indices_conflitantes)

        candidato = candidato.sort_values(
            "_periodo_fim_ordem", kind="stable", na_position="first"
        )

    resolvido = candidato.drop_duplicates(subset=[CHAVE_ITEM], keep="last")
    resolvido = resolvido.drop(columns=["_periodo_fim_ordem"], errors="ignore")
    resolvido = resolvido.reset_index(drop=True)

    return resolvido, {
        "versoes_substituidas": len(df) - len(resolvido) - len(conflitos),
        "arquivos": arquivos,
        "conflitos": conflitos.to_dict(orient="records"),
    }

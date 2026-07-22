"""Exportação de dados e KPIs para formatos de saída."""

import csv
import json
import re
from pathlib import Path
from typing import Union

import pandas as pd


_ACENTOS = {
    "á": "a", "à": "a", "ã": "a", "â": "a",
    "é": "e", "ê": "e", "í": "i", "ó": "o",
    "ô": "o", "õ": "o", "ú": "u", "ç": "c",
    "Á": "A", "À": "A", "Ã": "A", "Â": "A",
    "É": "E", "Ê": "E", "Í": "I", "Ó": "O",
    "Ô": "O", "Õ": "O", "Ú": "U", "Ç": "C",
}


def _limpar_acentos(texto: str) -> str:
    """Remove acentos de uma string."""
    for ac, sem in _ACENTOS.items():
        texto = texto.replace(ac, sem)
    return texto


def _snake_case(nome: str) -> str:
    """Converte nome de coluna para snake_case sem acentos."""
    nome = _limpar_acentos(nome)
    # CamelCase → separa com underscore
    nome = re.sub(r"([A-Z])", r"_\1", nome).lower().strip("_")
    # Espaços e underscores múltiplos → underscore simples
    nome = re.sub(r"[\s\-]+", "_", nome)
    nome = re.sub(r"_+", "_", nome)
    return nome.strip("_")


def _truncar(valor: object, max_len: int = 255) -> str:
    """Trunca string para max_len, retorna string."""
    if pd.isna(valor):
        return ""
    texto = str(valor)
    if len(texto) > max_len:
        texto = texto[:max_len]
    return texto


def export_to_csv_looker(
    df: pd.DataFrame,
    path: Union[str, Path],
    sep: str = ",",
    date_format: str = "%Y-%m-%d",
    max_str_len: int = 255,
) -> Path:
    """Exporta DataFrame para CSV formatado para Looker Studio (Google).

    Características:
      - UTF-8 puro (sem BOM)
      - Separador vírgula (,) — padrão Looker Studio / Google Sheets
      - Campos de texto entre aspas duplas
      - Datas no formato AAAA-MM-DD
      - Decimais com ponto (.)
      - Strings truncadas em max_str_len (evita overflow)
      - Cabeçalhos em snake_case sem acentos

    Args:
        df: DataFrame a exportar.
        path: Caminho do ficheiro de saída.
        sep: Separador de colunas (padrão ',').
        date_format: Formato de data (padrão AAAA-MM-DD).
        max_str_len: Limite de caracteres para strings.

    Returns:
        Path do ficheiro criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    export = df.copy()

    # 1. Converter cabeçalhos para snake_case sem acentos
    export.columns = [_snake_case(c) for c in export.columns]

    # 2. Formatar data_emissao para DD/MM/AAAA
    if "data_emissao" in export.columns:
        export["data_emissao"] = pd.to_datetime(
            export["data_emissao"], errors="coerce"
        )
        export["data_emissao"] = export["data_emissao"].dt.strftime(date_format)
        export["data_emissao"] = export["data_emissao"].fillna("")

    # 3. Truncar colunas de texto
    colunas_texto = export.select_dtypes(include=["object"]).columns
    for col in colunas_texto:
        export[col] = export[col].apply(lambda v: _truncar(v, max_str_len))

    # 4. Exportar CSV com quoting NONNUMERIC (texto entre aspas, números sem)
    export.to_csv(
        path,
        sep=sep,
        index=False,
        encoding="utf-8",
        quoting=csv.QUOTE_NONNUMERIC,
    )
    return path.resolve()


def export_to_csv(df: pd.DataFrame, path: Union[str, Path]) -> Path:
    """Exporta o DataFrame para CSV (UTF-8, separado por vírgulas).

    Args:
        df: DataFrame a exportar.
        path: Caminho do ficheiro de saída.

    Returns:
        Path do ficheiro criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path.resolve()


def export_to_json(
    df: pd.DataFrame,
    path: Union[str, Path],
    date_as_str: bool = True,
) -> Path:
    """Exporta o DataFrame para JSON (array de objetos).

    Args:
        df: DataFrame a exportar.
        path: Caminho do ficheiro de saída.
        date_as_str: Converter datas para string ISO.

    Returns:
        Path do ficheiro criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df_export = df.copy()
    if date_as_str and "data_emissao" in df_export.columns:
        df_export["data_emissao"] = df_export["data_emissao"].astype(str)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            json.loads(df_export.to_json(orient="records", force_ascii=False)),
            f,
            indent=2,
            ensure_ascii=False,
        )

    return path.resolve()


def export_to_markdown(kpis: dict, path: Union[str, Path]) -> Path:
    """Exporta KPIs para Markdown formatado.

    Args:
        kpis: Dict com métricas (formato de compute_kpis).
        path: Caminho do ficheiro de saída.

    Returns:
        Path do ficheiro criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas = [
        "# Relatório de KPIs — projetoAldebaran",
        "",
        "## Métricas Globais",
        "",
        f"| Métrica | Valor |",
        f"|---------|------:|",
        f"| Faturamento total | R$ {kpis.get('total_faturamento', 0):_.2f} |",
        f"| Notas fiscais | {kpis.get('qtd_notas_fiscais', 0):_} |",
        f"| Itens vendidos | {kpis.get('total_itens', 0):_} |",
        f"| Ticket médio | R$ {kpis.get('ticket_medio', 0):_.2f} |",
        "",
    ]

    top_valor = kpis.get("top_produtos_valor", [])
    if top_valor:
        linhas += [
            "## Top Produtos (por valor)",
            "",
            "| # | Código | Descrição | Total |",
            "|---|--------|-----------|------:|",
        ]
        for i, p in enumerate(top_valor[:10], 1):
            linhas.append(
                f"| {i} | {p['codigo']} | {p['descricao'][:60]} | "
                f"R$ {p['total']:_.2f} |"
            )
        linhas.append("")

    top_qtd = kpis.get("top_produtos_qtd", [])
    if top_qtd:
        linhas += [
            "## Top Produtos (por quantidade)",
            "",
            "| # | Código | Descrição | Total |",
            "|---|--------|-----------|------:|",
        ]
        for i, p in enumerate(top_qtd[:10], 1):
            linhas.append(
                f"| {i} | {p['codigo']} | {p['descricao'][:60]} | "
                f"{p['total']:_.0f} |"
            )
        linhas.append("")

    meses = kpis.get("vendas_por_mes", [])
    if meses:
        linhas += [
            "## Vendas por Mês",
            "",
            "| Mês | Total |",
            "|-----|------:|",
        ]
        for m in meses:
            linhas.append(f"| {m['mes']} | R$ {m['total']:_.2f} |")
        linhas.append("")

    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return path.resolve()

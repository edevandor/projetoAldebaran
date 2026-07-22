"""Exportação do dataset e dos KPIs para os formatos de consumo.

Duas camadas de saída, ambas derivadas do mesmo `SCHEMA_SAIDA`:

  - **Parquet** — formato principal. Tipado, comprimido e consultável por
    SQL local (DuckDB, Polars, pandas) sem servidor nem carga intermédia.
  - **CSV** — exportação secundária, para ferramentas de BI que não leem
    Parquet. Mesmo schema, serializado como texto.

JSON e Markdown servem a inspecção e relatório, não a análise.
"""

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from export.schema import CONTRATO_SAIDA, SCHEMA_SAIDA, aplicar_schema

__all__ = [
    "SCHEMA_SAIDA",
    "aplicar_schema",
    "export_to_parquet",
    "export_to_csv",
    "export_to_json",
    "export_to_markdown",
]


def _reais(centavos: int) -> Decimal:
    """Converte centavos inteiros apenas para apresentação."""
    return Decimal(centavos) / Decimal(100)


def _formatar_reais(centavos: int) -> str:
    return f"{_reais(centavos):,.2f}".replace(",", "_")


def export_to_parquet(
    df: pd.DataFrame,
    path: str | Path,
    compression: str = "snappy",
) -> Path:
    """Exporta o dataset para Parquet tipado, pronto para consulta SQL.

    Aplica `SCHEMA_SAIDA` antes de escrever: as datas vão como tipo
    temporal nativo (não string), o que permite filtrar e agregar por
    período em SQL sem CAST.

    Args:
        df: DataFrame consolidado.
        path: Caminho do arquivo de saída.
        compression: Codec de compressão do Parquet.

    Returns:
        Path do arquivo criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    canonico = aplicar_schema(df)
    tipos_arrow = {
        "string": pa.string(),
        "datetime64[ns]": pa.timestamp("ns"),
        "float64": pa.float64(),
        "int64": pa.int64(),
    }
    schema_arrow = pa.schema([
        pa.field(coluna, tipos_arrow[especificacao.dtype], nullable=especificacao.nullable)
        for coluna, especificacao in CONTRATO_SAIDA.items()
    ])
    tabela = pa.Table.from_pandas(
        canonico,
        schema=schema_arrow,
        preserve_index=False,
        safe=True,
    )
    pq.write_table(tabela, path, compression=compression)
    return path.resolve()


def export_to_csv(
    df: pd.DataFrame,
    path: str | Path,
    sep: str = ",",
    date_format: str = "%Y-%m-%d",
) -> Path:
    """Exporta o dataset para CSV padronizado, para consumo por BI.

    Convenções: UTF-8 sem BOM, separador vírgula, datas AAAA-MM-DD,
    decimais com ponto e aspas apenas onde necessário.

    Args:
        df: DataFrame consolidado.
        path: Caminho do arquivo de saída.
        sep: Separador de colunas.
        date_format: Formato de serialização das datas.

    Returns:
        Path do arquivo criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    aplicar_schema(df).to_csv(
        path,
        sep=sep,
        index=False,
        encoding="utf-8",
        date_format=date_format,
    )
    return path.resolve()


def export_to_json(
    df: pd.DataFrame,
    path: str | Path,
    date_as_str: bool = True,
) -> Path:
    """Exporta o DataFrame para JSON (array de objetos), para inspecção.

    Args:
        df: DataFrame a exportar.
        path: Caminho do arquivo de saída.
        date_as_str: Converter datas para string ISO.

    Returns:
        Path do arquivo criado.
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


def export_to_markdown(kpis: dict, path: str | Path) -> Path:
    """Exporta KPIs para Markdown formatado.

    Args:
        kpis: Dict com métricas (formato de `compute_kpis`).
        path: Caminho do arquivo de saída.

    Returns:
        Path do arquivo criado.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas = [
        "# Relatório de KPIs — projetoAldebaran",
        "",
        "## Métricas Globais",
        "",
        "| Métrica | Valor |",
        "|---------|------:|",
        f"| Faturamento total | R$ {_formatar_reais(kpis.get('total_faturamento_centavos', 0))} |",
        f"| Notas fiscais | {kpis.get('qtd_notas_fiscais', 0):_} |",
        f"| Itens vendidos | {kpis.get('total_itens', 0):_} |",
        f"| Ticket médio | R$ {_formatar_reais(kpis.get('ticket_medio_centavos', 0))} |",
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
                f"R$ {_formatar_reais(p['total_centavos'])} |"
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
            linhas.append(f"| {m['mes']} | R$ {_formatar_reais(m['total_centavos'])} |")
        linhas.append("")

    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return path.resolve()

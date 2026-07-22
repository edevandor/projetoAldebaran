"""Motor de consulta SQL local sobre o Parquet publicado.

O dataset publicado é consultado diretamente do arquivo Parquet, via
DuckDB, sem servidor, sem carga prévia e sem cópia em memória. A tabela
fica disponível sob o nome `vendas`.

Este é o ponto em que o dado deixa de ser um arquivo de relatório e
passa a ser uma base consultável.
"""

from pathlib import Path

import pandas as pd

PARQUET_PADRAO = Path("data/processed/vendas_consolidadas.parquet")
TABELA = "vendas"
TABELA_BASE = "_vendas_base"

# Consultas de demonstração — respondem às perguntas que motivaram o
# projeto e servem de ponto de partida para análise própria.
CONSULTAS: dict[str, str] = {
    "sazonalidade": """
        SELECT
            date_trunc('month', data_emissao) AS mes,
            COUNT(DISTINCT id_venda)          AS notas,
            SUM(valor_total_venda)            AS faturamento
        FROM vendas
        WHERE data_emissao IS NOT NULL
        GROUP BY mes
        ORDER BY mes
    """,
    "top-produtos": """
        SELECT
            codigo_produto,
            descricao_produto,
            SUM(quantidade)        AS quantidade,
            SUM(valor_total_venda) AS faturamento
        FROM vendas
        GROUP BY codigo_produto, descricao_produto
        ORDER BY faturamento DESC
        LIMIT 10
    """,
    "responsaveis": """
        SELECT
            responsavel,
            COUNT(DISTINCT id_venda)                            AS notas,
            SUM(valor_total_venda)                              AS faturamento,
            SUM(valor_total_venda) / COUNT(DISTINCT id_venda)   AS ticket_medio
        FROM vendas
        GROUP BY responsavel
        ORDER BY faturamento DESC
    """,
    "itens-por-nota": """
        SELECT
            itens_na_nota,
            COUNT(*) AS notas
        FROM (
            SELECT id_venda, COUNT(*) AS itens_na_nota
            FROM vendas
            GROUP BY id_venda
        )
        GROUP BY itens_na_nota
        ORDER BY itens_na_nota
    """,
    "cobertura": """
        SELECT
            COALESCE(sistema_origem, 'TOTAL')                     AS sistema_origem,
            MIN(data_emissao)                                     AS primeira_venda,
            MAX(data_emissao)                                     AS ultima_venda,
            COUNT(*)                                              AS itens,
            COUNT(DISTINCT id_venda)                              AS notas,
            SUM(CASE WHEN data_emissao IS NULL THEN 1 ELSE 0 END) AS itens_sem_data
        FROM vendas
        GROUP BY ROLLUP(sistema_origem)
        ORDER BY sistema_origem = 'TOTAL', sistema_origem
    """,
    "procedencia": """
        SELECT
            sistema_origem,
            confianca_data,
            COUNT(*)               AS itens,
            SUM(valor_total_venda) AS faturamento
        FROM vendas
        GROUP BY sistema_origem, confianca_data
        ORDER BY sistema_origem, itens DESC
    """,
}


def listar_consultas() -> list[str]:
    """Nomes das consultas de demonstração disponíveis."""
    return sorted(CONSULTAS)


def consultar(
    sql: str,
    parquet_path: str | Path = PARQUET_PADRAO,
) -> pd.DataFrame:
    """Executa SQL sobre o Parquet publicado e devolve o resultado.

    Args:
        sql: Consulta SQL, ou o nome de uma consulta de `CONSULTAS`.
        parquet_path: Caminho do Parquet a consultar.

    Returns:
        DataFrame com o resultado da consulta.

    Raises:
        FileNotFoundError: Se o Parquet ainda não foi gerado.
        ImportError: Se o DuckDB não estiver instalado.
    """
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ImportError(
            "DuckDB não instalado. Instale com: pip install duckdb"
        ) from exc

    caminho = Path(parquet_path)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Parquet não encontrado em {caminho}. "
            "Execute o pipeline primeiro: aldebaran run"
        )

    consulta = CONSULTAS.get(sql, sql)

    con = duckdb.connect()
    try:
        # Registado pela API de relações: o caminho não é interpolado em SQL.
        con.register(TABELA_BASE, con.read_parquet(str(caminho)))
        con.execute(
            f"""
            CREATE TEMP VIEW {TABELA} AS
            SELECT *,
                   CAST(valor_total_venda_centavos AS DECIMAL(18, 2)) / 100
                       AS valor_total_venda
            FROM {TABELA_BASE}
            """
        )
        return con.execute(consulta).fetchdf()
    finally:
        con.close()

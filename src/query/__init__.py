"""Consulta SQL local sobre o Parquet publicado pelo pipeline."""

from query.engine import CONSULTAS, consultar, listar_consultas

__all__ = ["CONSULTAS", "consultar", "listar_consultas"]

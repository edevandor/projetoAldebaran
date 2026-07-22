"""Ingestão de múltiplos ficheiros de um diretório.

Suporta .xlsx (openpyxl) e .xls (xlrd).
Consolida tudo num único DataFrame com rastreabilidade por ficheiro.
"""

from pathlib import Path
from typing import Union

import pandas as pd

from ingestion.parser import parse_xlsx


def _parse_file(path: Path) -> list[dict]:
    """Parseia um ficheiro, detectando o formato pela extensão."""
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return parse_xlsx(path)
    elif ext == ".xls":
        return _parse_xls(path)
    else:
        raise ValueError(f"Formato não suportado: {ext} em {path.name}")


def _parse_xls(path: Path) -> list[dict]:
    """Parseia ficheiro .xls (formato BIFF, JasperReports) — tabela plana."""
    import xlrd
    from datetime import datetime, timedelta

    def _serial_to_date(serial: float) -> datetime.date:
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=int(serial))).date()

    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_index(0)

    resultados = []
    for i in range(5, ws.nrows):
        row = [ws.cell_value(i, j) if ws.cell_type(i, j) != 0 else None
               for j in range(ws.ncols)]

        produto = str(row[0]).strip() if row[0] else ""
        if not produto or row[0] == "Produto":
            continue

        data_raw = row[7]
        if not isinstance(data_raw, (int, float)):
            continue

        resultados.append({
            "produto": produto,
            "data_emissao": _serial_to_date(data_raw),
            "tipo_documento": str(row[9]).strip().split("-", 1)[0] if row[9] else "",
            "numero_documento": str(row[9]).strip() if row[9] else "",
            "protocolo": str(int(row[8])).strip() if row[8] else "",
            "valor_total_venda": float(row[13]) if row[13] else 0.0,
            "quantidade": float(row[6]) if row[6] else 0.0,
            "unidade_medida": str(row[5]).strip() if row[5] else "",
        })

    return resultados


def ingest_directory(dir_path: Union[str, Path]) -> pd.DataFrame:
    """Lê todos os ficheiros XLSX/XLS de um diretório e consolida.

    Args:
        dir_path: Caminho para o diretório com ficheiros .xlsx ou .xls.

    Returns:
        DataFrame com todas as vendas concatenadas.
        Coluna 'arquivo_origem' indica o nome do ficheiro de origem.
        Retorna DataFrame vazio se não houver ficheiros.
    """
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Diretório não encontrado: {dir_path}")

    ficheiros = sorted(dir_path.glob("*.xlsx")) + sorted(dir_path.glob("*.xls")) + sorted(dir_path.glob("*.Xls"))
    if not ficheiros:
        return pd.DataFrame()

    todas_as_vendas: list[pd.DataFrame] = []
    for f in ficheiros:
        dados = _parse_file(f)
        if not dados:
            continue
        df = pd.DataFrame(dados)
        df["arquivo_origem"] = f.name
        todas_as_vendas.append(df)

    if not todas_as_vendas:
        return pd.DataFrame()

    return pd.concat(todas_as_vendas, ignore_index=True)

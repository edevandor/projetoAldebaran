"""Ingestão de múltiplos arquivos de um diretório.

Suporta .xlsx (openpyxl) e .xls (xlrd).
Consolida tudo num único DataFrame com rastreabilidade por arquivo.
"""

import datetime
from collections.abc import Iterable, Sequence
from pathlib import Path

import pandas as pd

from ingestion.parser import parse_xlsx


def _parse_file(path: Path) -> list[dict]:
    """Parseia um arquivo, detectando o formato pela extensão."""
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return parse_xlsx(path)
    elif ext == ".xls":
        return _parse_xls(path)
    else:
        raise ValueError(f"Formato não suportado: {ext} em {path.name}")


ROTULOS_NAO_DADOS = ("produto", "total", "artigo:", "responsavel:", "responsável:")


def _eh_linha_de_dados_xls(produto: str, documento: object, valor: object) -> bool:
    """Distingue uma linha de venda de cabeçalho, subtotal e metadado.

    Substitui a contagem fixa de linhas a pular: o número de linhas de
    cabeçalho varia entre exportações, e pular uma quantidade fixa faz o
    parser perder vendas ou ler rótulos como se fossem dados.

    Uma venda tem produto e, ao menos, documento ou valor numérico — o que
    descarta as linhas de metadado do topo do relatório.
    """
    if not produto:
        return False
    if produto.strip().lower().startswith(ROTULOS_NAO_DADOS):
        return False

    tem_documento = bool(str(documento).strip()) if documento is not None else False
    tem_valor = isinstance(valor, (int, float)) and not isinstance(valor, bool)
    return tem_documento or tem_valor


def _campo(valores: Sequence, indice: int):
    """Célula da coluna, ou None se a linha terminar antes dela."""
    return valores[indice] if len(valores) > indice else None


def _serial_para_data(serial: float) -> datetime.date:
    """Converte o serial de data do Excel para date."""
    base = datetime.datetime(1899, 12, 30)
    return (base + datetime.timedelta(days=int(serial))).date()


def _numero_ou_ausente(valor: object) -> float | None:
    """Preserva ausência e conversão inválida para a validação posterior."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def extrair_registros_xls(linhas: Iterable[Sequence]) -> list[dict]:
    """Extrai os registros de venda de uma tabela plana do formato .xls.

    Recebe as linhas já lidas, sem depender do xlrd — o que torna o
    comportamento verificável sem um arquivo .xls binário.

    Linhas sem data são **preservadas** com `data_emissao` nula, e não
    descartadas: a migração de servidor de 2023 deixou vendas sem datação,
    e removê-las em silêncio apagaria faturamento real. A decisão sobre
    elas é da validação (ver DECISIONS.md, D-012).
    """
    resultados: list[dict] = []

    for row in linhas:
        valores = list(row)
        produto = str(valores[0]).strip() if valores and valores[0] else ""
        if not _eh_linha_de_dados_xls(produto, _campo(valores, 9), _campo(valores, 13)):
            continue

        data_raw = _campo(valores, 7)
        data_emissao = (
            _serial_para_data(data_raw)
            if isinstance(data_raw, (int, float)) and not isinstance(data_raw, bool)
            else None
        )

        documento = str(_campo(valores, 9)).strip() if _campo(valores, 9) else ""
        protocolo_raw = _campo(valores, 8)
        if isinstance(protocolo_raw, float):
            protocolo = str(int(protocolo_raw))
        elif protocolo_raw:
            protocolo = str(protocolo_raw).strip()
        else:
            protocolo = ""

        resultados.append({
            "produto": produto,
            "data_emissao": data_emissao,
            "tipo_documento": documento.split("-", 1)[0] if documento else "",
            "numero_documento": documento,
            "protocolo": protocolo,
            "valor_total_venda": _numero_ou_ausente(_campo(valores, 13)),
            "quantidade": _numero_ou_ausente(_campo(valores, 6)),
            "unidade_medida": str(_campo(valores, 5)).strip() if _campo(valores, 5) else "",
        })

    return resultados


def _parse_xls(path: Path) -> list[dict]:
    """Lê um arquivo .xls (formato BIFF) e extrai os registros de venda."""
    import xlrd

    wb = xlrd.open_workbook(str(path))
    ws = wb.sheet_by_index(0)

    linhas = [
        [
            ws.cell_value(i, j) if ws.cell_type(i, j) != 0 else None
            for j in range(ws.ncols)
        ]
        for i in range(ws.nrows)
    ]
    return extrair_registros_xls(linhas)


def ingest_directory(dir_path: str | Path) -> pd.DataFrame:
    """Lê todos os arquivos XLSX/XLS de um diretório e consolida.

    Args:
        dir_path: Caminho para o diretório com arquivos .xlsx ou .xls.

    Returns:
        DataFrame com todas as vendas concatenadas.
        Coluna 'arquivo_origem' indica o nome do arquivo de origem.
        Retorna DataFrame vazio se não houver arquivos.
    """
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Diretório não encontrado: {dir_path}")

    arquivos = (
        sorted(dir_path.glob("*.xlsx"))
        + sorted(dir_path.glob("*.xls"))
        + sorted(dir_path.glob("*.Xls"))
    )
    if not arquivos:
        return pd.DataFrame()

    todas_as_vendas: list[pd.DataFrame] = []
    for f in arquivos:
        dados = _parse_file(f)
        if not dados:
            continue
        df = pd.DataFrame(dados)
        df["arquivo_origem"] = f.name
        datas = pd.to_datetime(df["data_emissao"], errors="coerce").dropna()
        if datas.empty:
            df["periodo_inicio"] = None
            df["periodo_fim"] = None
            df["confianca_metadados"] = "AUSENTE"
        else:
            df["periodo_inicio"] = datas.min().date()
            df["periodo_fim"] = datas.max().date()
            df["confianca_metadados"] = "DERIVADA"
        todas_as_vendas.append(df)

    if not todas_as_vendas:
        return pd.DataFrame()

    consolidado = pd.concat(todas_as_vendas, ignore_index=True)
    # Procedência: no relatório atual a data é lida, não inferida.
    consolidado["sistema_origem"] = "ATUAL"
    consolidado["confianca_data"] = consolidado["data_emissao"].map(
        lambda valor: "Ausente" if valor is None or pd.isna(valor) else "Registrada"
    )
    return consolidado

"""Benchmark reproduzível do núcleo tabular; não mede parsing dos arquivos de origem."""

import argparse
import json
import resource
import tempfile
import time
from datetime import date
from pathlib import Path

import pandas as pd

from analytics.kpis import compute_kpis
from export.formatters import export_to_parquet
from transformation.standardizer import standardize
from validation.validator import validate_and_partition


def benchmark(rows: int) -> dict:
    """Mede padronização, validação, KPIs e Parquet sobre volume configurável."""
    base = pd.DataFrame({
        "produto": [f"{i % 1000:06d} - PRODUTO {i % 1000}" for i in range(rows)],
        "data_emissao": [date(2025, 1, 1)] * rows,
        "tipo_documento": ["001"] * rows,
        "numero_documento": [f"001-{i // 4:09d}" for i in range(rows)],
        "protocolo": [str(i) for i in range(rows)],
        "valor_total_venda": [100.0] * rows,
        "quantidade": [1.0] * rows,
        "unidade_medida": ["UN"] * rows,
        "responsavel": ["Responsável A"] * rows,
        "artigo": ["Categoria A"] * rows,
        "arquivo_origem": ["benchmark.xlsx"] * rows,
        "sistema_origem": ["ATUAL"] * rows,
        "confianca_data": ["Registrada"] * rows,
        "id_execucao": ["benchmark"] * rows,
    })
    inicio = time.perf_counter()
    df = standardize(base)
    df, rejeitados, _ = validate_and_partition(df)
    compute_kpis(df)
    with tempfile.TemporaryDirectory() as tmp:
        export_to_parquet(df, Path(tmp) / "benchmark.parquet")
    return {
        "escopo": "núcleo tabular, sem parsing XLSX/XLS/REL",
        "linhas": rows,
        "rejeitadas": len(rejeitados),
        "duracao_s": round(time.perf_counter() - inicio, 3),
        "pico_memoria_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    print(json.dumps(benchmark(parser.parse_args().rows), ensure_ascii=False, indent=2))

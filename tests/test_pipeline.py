"""Contratos da orquestração entre as etapas do pipeline."""

from datetime import date

import pandas as pd

from export.schema import SCHEMA_SAIDA
from pipeline import run_pipeline


def test_versao_invalida_recente_nao_remove_versao_valida(tmp_path, monkeypatch):
    base = {
        "data_emissao": date(2025, 1, 15),
        "tipo_documento": "001",
        "numero_documento": "001-100001",
        "protocolo": "P1",
        "quantidade": 1.0,
        "unidade_medida": "UN",
        "responsavel": "Responsável A",
        "artigo": "Categoria A",
        "sistema_origem": "ATUAL",
        "confianca_data": "Registrada",
        "periodo_inicio": date(2025, 1, 1),
        "confianca_metadados": "DECLARADA",
    }
    entrada = pd.DataFrame([
        {
            **base,
            "produto": "000101 - PRODUTO ALFA",
            "valor_total_venda": 100.0,
            "arquivo_origem": "versao_valida.xlsx",
            "periodo_fim": date(2025, 1, 31),
        },
        {
            **base,
            "produto": "",
            "valor_total_venda": 110.0,
            "arquivo_origem": "versao_invalida.xlsx",
            "periodo_fim": date(2025, 2, 28),
        },
    ])
    monkeypatch.setattr("pipeline.ingest_directory", lambda _: entrada)

    resultado = run_pipeline(
        data_dir=tmp_path,
        output_dir=tmp_path / "processed",
        legado_dir=None,
    )

    assert list(resultado["dados"]["arquivo_origem"]) == ["versao_valida.xlsx"]
    assert resultado["status"] == "PARCIAL"
    assert resultado["validacao"].rejected_rows == 1


def test_dataframe_retornado_e_o_mesmo_contrato_publicado(tmp_path):
    resultado = run_pipeline(
        data_dir="tests/fixtures",
        output_dir=tmp_path / "processed",
        legado_dir=None,
    )
    publicado = pd.read_parquet(
        tmp_path / "processed" / "vendas_consolidadas.parquet"
    )

    assert list(resultado["dados"].columns) == list(SCHEMA_SAIDA)
    pd.testing.assert_frame_equal(
        resultado["dados"].reset_index(drop=True),
        publicado.reset_index(drop=True),
        check_dtype=True,
    )

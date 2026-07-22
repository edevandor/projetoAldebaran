"""Fixtures compartilhadas para testes do módulo de ingestão."""

from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mapa_vendas_path() -> Path:
    """Caminho para o XLSX sintético de teste (2 artigos, 5 vendas)."""
    return FIXTURES_DIR / "mapa_vendas_teste.xlsx"


@pytest.fixture
def diretorio_vazio(tmp_path) -> Path:
    """Diretório temporário vazio."""
    return tmp_path

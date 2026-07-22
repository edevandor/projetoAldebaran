"""Testes do módulo parser_rel_analitico — funções auxiliares de parsing."""

import pytest

from ingestion.parser_rel_analitico import (
    _parse_br_num,
    _parse_data_br,
)


class TestParseBrNum:
    """Testes para conversão de números no formato brasileiro."""

    def test_numero_simples(self):
        assert _parse_br_num("1.234,56") == 1234.56

    def test_numero_sem_milhar(self):
        assert _parse_br_num("12,50") == 12.5

    def test_numero_inteiro(self):
        assert _parse_br_num("35") == 35.0

    def test_numero_negativo(self):
        assert _parse_br_num("-239,96") == -239.96

    def test_valor_vazio(self):
        assert _parse_br_num("") == 0.0

    def test_valor_com_espacos(self):
        assert _parse_br_num("  1.000,00  ") == 1000.0


class TestParseDataBR:
    """Testes para parsing de data dd/mm/aa."""

    def test_data_valida(self):
        assert _parse_data_br("01/02/02") == (1, 2, "02")

    def test_data_com_espacos(self):
        assert _parse_data_br("  01/02/02  ") == (1, 2, "02")

    def test_data_vazia(self):
        assert _parse_data_br("") is None

    def test_data_mal_formatada(self):
        assert _parse_data_br("31/12") is None


# Testes com dados de exemplo .rel removidos intencionalmente.
# Os dados sao confidenciais e nao podem ser versionados.
# Testes sinteticos equivalentes seriam possiveis com geracao
# de ficheiros .rel de exemplo, mas nao ha prioridade atual.

"""Testes do módulo de ingestão — parser de XLSX hierárquico."""

from datetime import date
from pathlib import Path

import pytest

from ingestion.parser import parse_xlsx


class TestParseXLSX:
    """Suite de testes para o parser de ficheiro único."""

    def test_extrai_numero_correto_de_vendas(self, mapa_vendas_path: Path):
        """Deve extrair exatamente 5 linhas de venda (2 artigos: 3+2)."""
        resultado = parse_xlsx(mapa_vendas_path)
        assert len(resultado) == 5, (
            f"Esperado 5 vendas, obtido {len(resultado)}"
        )

    def test_ignora_metadados_e_totais(self, mapa_vendas_path: Path):
        """Não deve incluir linhas de metadados, cabeçalhos ou totais."""
        resultado = parse_xlsx(mapa_vendas_path)
        descricoes = [r["produto"] for r in resultado]
        for item in descricoes:
            assert not item.startswith("Artigo:"), (
                f"Linha de artigo incluída: {item}"
            )
            assert not item.startswith("Total:"), (
                f"Linha de total incluída: {item}"
            )
            assert not item.startswith("Produto"), (
                f"Cabeçalho incluído: {item}"
            )

    def test_mapeia_coluna_produto(self, mapa_vendas_path: Path):
        """Campo 'produto' deve conter código + descrição."""
        resultado = parse_xlsx(mapa_vendas_path)
        primeiro = resultado[0]["produto"]
        assert "FERRAMENTA" in primeiro, (
            f"Produto esperado não encontrado: {primeiro}"
        )

    def test_mapeia_data_emissao(self, mapa_vendas_path: Path):
        """Campo 'data_emissao' deve ser do tipo date."""
        resultado = parse_xlsx(mapa_vendas_path)
        for r in resultado:
            assert isinstance(r["data_emissao"], date), (
                f"data_emissao não é date: {type(r['data_emissao'])}"
            )

    def test_mapeia_numero_documento(self, mapa_vendas_path: Path):
        """Campo 'numero_documento' deve vir da coluna NF Nº."""
        resultado = parse_xlsx(mapa_vendas_path)
        assert resultado[0]["numero_documento"] == "001-100001"

    def test_mapeia_valor_total_venda(self, mapa_vendas_path: Path):
        """Campo 'valor_total_venda' deve ser numérico."""
        resultado = parse_xlsx(mapa_vendas_path)
        for r in resultado:
            assert isinstance(r["valor_total_venda"], (int, float)), (
                f"valor_total_venda não numérico: {type(r['valor_total_venda'])}"
            )

    def test_mapeia_quantidade_quando_presente(self, mapa_vendas_path: Path):
        """Campo 'quantidade' deve refletir a coluna Quantidade."""
        resultado = parse_xlsx(mapa_vendas_path)
        # Primeira venda: quantidade=2
        assert resultado[0]["quantidade"] == 2

    def test_protocolo_quando_presente(self, mapa_vendas_path: Path):
        """Campo 'protocolo' deve ser string quando presente."""
        resultado = parse_xlsx(mapa_vendas_path)
        assert isinstance(resultado[0]["protocolo"], str)
        assert len(resultado[0]["protocolo"]) > 0

    def test_chaves_do_dicionario(self, mapa_vendas_path: Path):
        """Cada registro deve conter todas as chaves do modelo de dados."""
        chaves_esperadas = {
            "produto", "data_emissao", "tipo_documento",
            "numero_documento", "protocolo", "valor_total_venda",
            "quantidade", "unidade_medida",
            "responsavel", "artigo",
        }
        resultado = parse_xlsx(mapa_vendas_path)
        for r in resultado:
            chaves_obtidas = set(r.keys())
            assert chaves_esperadas.issubset(chaves_obtidas), (
                f"Chaves faltando: {chaves_esperadas - chaves_obtidas}"
            )

    def test_responsavel_presente(self, mapa_vendas_path: Path):
        """Cada venda deve ter o responsável herdado."""
        resultado = parse_xlsx(mapa_vendas_path)
        for r in resultado:
            assert isinstance(r["responsavel"], str)
            assert len(r["responsavel"]) > 0, (
                f"responsavel vazio na venda: {r}"
            )

    def test_artigo_presente(self, mapa_vendas_path: Path):
        """Cada venda deve ter o artigo (categoria) herdado."""
        resultado = parse_xlsx(mapa_vendas_path)
        for r in resultado:
            assert isinstance(r["artigo"], str)
            assert len(r["artigo"]) > 0, (
                f"artigo vazio na venda: {r}"
            )

    def test_responsavel_e_artigo_corretos(self, mapa_vendas_path: Path):
        """Valores de responsavel e artigo devem reflectir a hierarquia."""
        resultado = parse_xlsx(mapa_vendas_path)
        # Primeiras 3 vendas: Responsavel=TESTE, Artigo=FERRAMENTA A
        for r in resultado[:3]:
            assert r["responsavel"] == "TESTE", (
                f"Esperado TESTE, obtido {r['responsavel']}"
            )
            assert r["artigo"] == "FERRAMENTA A", (
                f"Esperado FERRAMENTA A, obtido {r['artigo']}"
            )
        # Últimas 2 vendas: Responsavel=TESTE, Artigo=PARAFUSO B
        for r in resultado[3:]:
            assert r["responsavel"] == "TESTE", (
                f"Esperado TESTE, obtido {r['responsavel']}"
            )
            assert r["artigo"] == "PARAFUSO B", (
                f"Esperado PARAFUSO B, obtido {r['artigo']}"
            )

    def test_unidade_medida_opcional(self, mapa_vendas_path: Path):
        """unidade_medida pode ser string vazia quando ausente."""
        resultado = parse_xlsx(mapa_vendas_path)
        # Todas têm "UN" ou "PC"
        assert resultado[0]["unidade_medida"] in ("UN", "PC", "")


from ingestion.directory import ingest_directory


class TestIngestDirectory:
    """Suite de testes para ingestão de diretório."""

    def test_diretorio_vazio_retorna_dataframe_vazio(self, diretorio_vazio):
        """Diretório sem ficheiros XLSX retorna DataFrame vazio."""
        df = ingest_directory(str(diretorio_vazio))
        assert len(df) == 0

    def test_concatena_multiplos_ficheiros(self, mapa_vendas_path: Path, tmp_path):
        """Dois ficheiros são concatenados no mesmo DataFrame."""
        import shutil
        f1 = tmp_path / "a.xlsx"
        f2 = tmp_path / "b.xlsx"
        shutil.copy2(mapa_vendas_path, f1)
        shutil.copy2(mapa_vendas_path, f2)
        df = ingest_directory(str(tmp_path))
        assert len(df) == 10  # 5 vendas x 2 ficheiros

    def test_coluna_arquivo_origem_presente(self, mapa_vendas_path: Path, tmp_path):
        """Cada linha tem coluna 'arquivo_origem' com o nome do ficheiro."""
        import shutil
        f1 = tmp_path / "a.xlsx"
        shutil.copy2(mapa_vendas_path, f1)
        df = ingest_directory(str(tmp_path))
        assert "arquivo_origem" in df.columns
        assert all(df["arquivo_origem"] == "a.xlsx")

    def test_coluna_arquivo_origem_distinta_por_ficheiro(
        self, mapa_vendas_path: Path, tmp_path
    ):
        """Ficheiros diferentes têm valores diferentes em arquivo_origem."""
        import shutil
        f1 = tmp_path / "alfa.xlsx"
        f2 = tmp_path / "beta.xlsx"
        shutil.copy2(mapa_vendas_path, f1)
        shutil.copy2(mapa_vendas_path, f2)
        df = ingest_directory(str(tmp_path))
        origens = df["arquivo_origem"].unique()
        assert sorted(origens) == ["alfa.xlsx", "beta.xlsx"]

    def test_dataframe_tem_as_mesmas_colunas_do_parser(
        self, mapa_vendas_path: Path, tmp_path
    ):
        """DataFrame consolidado mantém as mesmas colunas do parser."""
        import shutil
        f1 = tmp_path / "a.xlsx"
        shutil.copy2(mapa_vendas_path, f1)
        df = ingest_directory(str(tmp_path))
        assert "produto" in df.columns
        assert "data_emissao" in df.columns
        assert "valor_total_venda" in df.columns

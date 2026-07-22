"""Testes do módulo de exportação — JSON e Markdown."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from export.formatters import export_to_json, export_to_markdown, export_to_csv


class TestExportToJSON:
    """Suite de testes para exportação JSON."""

    def _df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "produto": "0000001 - FERRAMENTA A",
                "codigo_produto": "0000001",
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 150.0,
                "quantidade": 2,
            }
        ])

    def test_cria_arquivo_json(self, tmp_path: Path):
        """export_to_json cria um ficheiro JSON no caminho especificado."""
        path = tmp_path / "saida.json"
        resultado = export_to_json(self._df(), path)
        assert resultado.exists()
        assert resultado.suffix == ".json"

    def test_json_contem_registros(self, tmp_path: Path):
        """JSON gerado contém os registos do DataFrame."""
        path = tmp_path / "saida.json"
        export_to_json(self._df(), path)
        with open(path, encoding="utf-8") as f:
            dados = json.load(f)
        assert len(dados) == 1
        assert dados[0]["codigo_produto"] == "0000001"

    def test_data_convertida_para_string(self, tmp_path: Path):
        """Data é convertida para string ISO."""
        path = tmp_path / "saida.json"
        export_to_json(self._df(), path)
        with open(path, encoding="utf-8") as f:
            dados = json.load(f)
        assert isinstance(dados[0]["data_emissao"], str)
        assert "2025-01-15" in dados[0]["data_emissao"]

    def test_dataframe_vazio_cria_json_vazio(self, tmp_path: Path):
        """DataFrame vazio gera array JSON vazio."""
        df = pd.DataFrame(columns=["produto", "valor_total_venda"])
        path = tmp_path / "vazio.json"
        export_to_json(df, path)
        with open(path, encoding="utf-8") as f:
            dados = json.load(f)
        assert dados == []

    def test_cria_diretorio_intermediario(self, tmp_path: Path):
        """Cria diretórios intermédios se não existirem."""
        path = tmp_path / "sub" / "pasta" / "saida.json"
        export_to_json(self._df(), path)
        assert path.exists()


class TestExportToCSV:
    """Suite de testes para exportação CSV."""

    def _df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "produto": "0000001 - FERRAMENTA A",
                "codigo_produto": "0000001",
                "data_emissao": date(2025, 1, 15),
                "valor_total_venda": 150.0,
                "quantidade": 2,
                "responsavel": "TESTE",
                "artigo": "FERRAMENTA A",
            }
        ])

    def test_cria_arquivo_csv(self, tmp_path: Path):
        """export_to_csv cria um ficheiro CSV no caminho especificado."""
        path = tmp_path / "saida.csv"
        resultado = export_to_csv(self._df(), path)
        assert resultado.exists()
        assert resultado.suffix == ".csv"

    def test_csv_tem_cabecalho_e_dados(self, tmp_path: Path):
        """CSV gerado contém cabeçalho e dados."""
        path = tmp_path / "saida.csv"
        export_to_csv(self._df(), path)
        conteudo = path.read_text(encoding="utf-8-sig")
        assert "produto" in conteudo
        assert "FERRAMENTA" in conteudo
        assert "TESTE" in conteudo

    def test_csv_separado_por_virgula(self, tmp_path: Path):
        """CSV usa vírgula como separador."""
        path = tmp_path / "saida.csv"
        export_to_csv(self._df(), path)
        linhas = path.read_text(encoding="utf-8-sig").strip().split("\n")
        cabecalho = linhas[0]
        assert cabecalho.count(",") >= 3

    def test_csv_vazio_cria_cabecalho(self, tmp_path: Path):
        """DataFrame vazio gera CSV apenas com cabeçalho."""
        df = pd.DataFrame(columns=["produto", "valor"])
        path = tmp_path / "vazio.csv"
        export_to_csv(df, path)
        linhas = path.read_text(encoding="utf-8-sig").strip().split("\n")
        assert len(linhas) == 1  # só cabeçalho
        assert "produto" in linhas[0]

    def test_cria_diretorio_intermediario(self, tmp_path: Path):
        """Cria diretórios intermédios se não existirem."""
        path = tmp_path / "sub" / "pasta" / "saida.csv"
        export_to_csv(self._df(), path)
        assert path.exists()


class TestExportToMarkdown:
    """Suite de testes para exportação Markdown."""

    def _kpis(self) -> dict:
        return {
            "total_faturamento": 10000.0,
            "qtd_notas_fiscais": 15,
            "total_itens": 50,
            "ticket_medio": 666.67,
            "top_produtos_valor": [
                {"codigo": "0001", "descricao": "PRODUTO TOP", "total": 5000.0},
                {"codigo": "0002", "descricao": "PRODUTO B", "total": 3000.0},
            ],
            "top_produtos_qtd": [
                {"codigo": "0003", "descricao": "UNIDADE", "total": 100.0},
            ],
            "vendas_por_mes": [
                {"mes": "2025-01", "total": 5000.0},
                {"mes": "2025-02", "total": 5000.0},
            ],
        }

    def test_cria_arquivo_markdown(self, tmp_path: Path):
        """export_to_markdown cria ficheiro .md."""
        path = tmp_path / "relatorio.md"
        resultado = export_to_markdown(self._kpis(), path)
        assert resultado.exists()
        assert resultado.suffix == ".md"

    def test_markdown_tem_titulo(self, tmp_path: Path):
        """Arquivo MD começa com título."""
        path = tmp_path / "relatorio.md"
        export_to_markdown(self._kpis(), path)
        conteudo = path.read_text(encoding="utf-8")
        assert "# Relatório de KPIs" in conteudo

    def test_markdown_tem_metricas_globais(self, tmp_path: Path):
        """Métricas globais aparecem no markdown."""
        path = tmp_path / "relatorio.md"
        export_to_markdown(self._kpis(), path)
        conteudo = path.read_text(encoding="utf-8")
        assert "R$ 10_000.00" in conteudo
        assert "15" in conteudo

    def test_markdown_sem_top_produtos(self, tmp_path: Path):
        """KPIs sem top produtos não quebram a exportação."""
        kpis = {"total_faturamento": 0, "qtd_notas_fiscais": 0,
                "total_itens": 0, "ticket_medio": 0}
        path = tmp_path / "minimo.md"
        export_to_markdown(kpis, path)
        conteudo = path.read_text(encoding="utf-8")
        assert conteudo


class TestPipelineIntegration:
    """Testes de regressão — pipeline completo."""

    def test_pipeline_com_dados_sinteticos(self):
        """Pipeline completo funciona com dados sintéticos da fixture."""
        from ingestion.directory import ingest_directory
        from transformation.standardizer import standardize
        from consolidation.consolidator import consolidate
        from analytics.kpis import compute_kpis

        df = ingest_directory("tests/fixtures")
        assert len(df) > 0, "Deveria ter lido o ficheiro de teste"
        df = standardize(df)
        assert "id_venda" in df.columns
        df, _ = consolidate(df)
        kpis = compute_kpis(df)
        assert kpis["total_faturamento"] > 0
        assert kpis["qtd_notas_fiscais"] > 0

    def test_pipeline_orquestrada(self):
        """run_pipeline executa todas as etapas."""
        import tempfile
        from pathlib import Path
        from src.pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            resultado = run_pipeline("tests/fixtures", output_dir=tmp_p / "processed", csv_path=tmp_p / "dados.csv")
            assert "dados" in resultado
            assert "kpis" in resultado
            assert "etapas" in resultado
            assert len(resultado["dados"]) > 0
            assert resultado["kpis"]["total_faturamento"] > 0

    def test_etapas_no_relatorio(self):
        """Relatório de etapas contém todas as fases."""
        import tempfile
        from pathlib import Path
        from src.pipeline import run_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            resultado = run_pipeline("tests/fixtures", output_dir=tmp_p / "processed", csv_path=tmp_p / "dados.csv")
            etapas = resultado["etapas"]
            for etapa in ["ingestao", "padronizacao", "consolidacao", "analytics"]:
                assert etapa in etapas, f"Etapa {etapa} ausente"
                assert "duracao_s" in etapas[etapa], \
                    f"duração ausente em {etapa}"

    def test_export_apos_pipeline(self, tmp_path: Path):
        """Exportar JSON + MD após pipeline funciona."""
        import tempfile
        from src.pipeline import run_pipeline
        from export.formatters import export_to_json, export_to_markdown

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            resultado = run_pipeline("tests/fixtures", output_dir=tmp_p / "processed", csv_path=tmp_p / "dados.csv")
            json_path = tmp_path / "dados.json"
            md_path = tmp_path / "kpis.md"
            export_to_json(resultado["dados"], json_path)
            export_to_markdown(resultado["kpis"], md_path)
            assert json_path.exists()
            assert "R$" in md_path.read_text(encoding="utf-8")


class TestAuditIntegration:
    """Testes para o módulo de auditoria."""

    def test_pipeline_run_criado(self):
        """criar_relatorio_pipeline produz PipelineRun."""
        from audit.auditor import criar_relatorio_pipeline

        etapas = {
            "ingestao": {"linhas": 100, "duracao_s": 2.5},
            "padronizacao": {"linhas": 100, "duracao_s": 0.3},
        }
        run = criar_relatorio_pipeline(etapas)
        assert run.sucesso
        assert run.duracao_s == 2.8
        assert "ingestao" in run.etapas

    def test_pipeline_run_com_erros(self):
        """PipelineRun com erros relata status de falha."""
        from audit.auditor import PipelineRun

        run = PipelineRun(erros=["Ficheiro não encontrado"])
        assert not run.sucesso
        assert "✗" in run.resumo()

    def test_resumo_contem_etapas(self):
        """Resumo mostra número de etapas."""
        from audit.auditor import criar_relatorio_pipeline

        etapas = {"ingestao": {"linhas": 50, "duracao_s": 1.0}}
        run = criar_relatorio_pipeline(etapas)
        resumo = run.resumo()
        assert "1 etapas" in resumo
        assert "50 linhas" in resumo

    def test_audit_com_pipeline_real(self):
        """Auditoria integrada com pipeline real coleta métricas."""
        import tempfile
        from src.pipeline import run_pipeline
        from audit.auditor import criar_relatorio_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            resultado = run_pipeline("tests/fixtures", output_dir=tmp_p / "processed", csv_path=tmp_p / "dados.csv")
            run = criar_relatorio_pipeline(resultado["etapas"])
            assert run.sucesso
            assert run.duracao_s > 0
            assert len(run.etapas) >= 4

"""Testes da interface de linha de comando."""

import json
from pathlib import Path

import pytest

from cli import main


class TestDemo:
    def test_gera_xlsx_e_legado(self, tmp_path: Path, capsys):
        codigo = main([
            "demo",
            "--raw-dir", str(tmp_path / "raw"),
            "--legado-dir", str(tmp_path / "legado"),
        ])
        assert codigo == 0
        assert (tmp_path / "raw" / "vendas_sinteticas.xlsx").exists()
        assert len(list((tmp_path / "legado").glob("*.rel"))) == 3

    def test_sem_legado(self, tmp_path: Path, capsys):
        main([
            "demo",
            "--raw-dir", str(tmp_path / "raw"),
            "--legado-dir", str(tmp_path / "legado"),
            "--sem-legado",
        ])
        assert not (tmp_path / "legado").exists()

    def test_saida_reproduzivel_por_semente(self, tmp_path: Path):
        """Mesma semente, mesmos dados.

        A comparação é sobre o conteúdo extraído, não sobre os bytes do
        arquivo: o XLSX carrega um timestamp de criação nos metadados.
        """
        from ingestion.parser import parse_xlsx

        main(["demo", "--raw-dir", str(tmp_path / "a"), "--sem-legado", "--seed", "7"])
        main(["demo", "--raw-dir", str(tmp_path / "b"), "--sem-legado", "--seed", "7"])

        primeiro = parse_xlsx(tmp_path / "a" / "vendas_sinteticas.xlsx")
        segundo = parse_xlsx(tmp_path / "b" / "vendas_sinteticas.xlsx")

        assert primeiro == segundo
        assert len(primeiro) > 0


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    """Diretório com dados de demonstração já gerados."""
    main(["demo", "--raw-dir", str(tmp_path / "raw"), "--sem-legado"])
    return tmp_path


class TestRun:
    def test_ajuda_declara_output_como_diretorio(self, capsys):
        with pytest.raises(SystemExit, match="0"):
            main(["run", "--help"])

        assert "diretório de publicação" in capsys.readouterr().out

    def test_publica_parquet(self, projeto: Path, capsys):
        codigo = main([
            "run",
            "-i", str(projeto / "raw"),
            "-o", str(projeto / "processed"),
        ])
        assert codigo == 0
        assert (projeto / "processed" / "vendas_consolidadas.parquet").exists()

    def test_nao_gera_csv_sem_pedido(self, projeto: Path, capsys):
        """Parquet é o formato principal; o CSV só sai quando pedido."""
        main(["run", "-i", str(projeto / "raw"), "-o", str(projeto / "processed")])
        assert not list(projeto.rglob("*.csv"))

    def test_gera_csv_quando_pedido(self, projeto: Path, capsys):
        main([
            "run",
            "-i", str(projeto / "raw"),
            "-o", str(projeto / "processed"),
            "--csv",
            "--csv-path", str(projeto / "exports" / "vendas.csv"),
        ])
        assert (projeto / "exports" / "vendas.csv").exists()

    def test_grava_auditoria_da_execucao(self, projeto: Path, capsys):
        main(["run", "-i", str(projeto / "raw"), "-o", str(projeto / "processed")])
        assert (projeto / "processed" / "execucao.json").exists()

    def test_diretorio_sem_vendas_retorna_erro_legivel(self, tmp_path: Path, capsys):
        origem = tmp_path / "raw"
        origem.mkdir()

        codigo = main([
            "run",
            "-i", str(origem),
            "-o", str(tmp_path / "processed"),
            "--sem-legado",
        ])

        assert codigo == 1
        assert "Nenhum registro de venda" in capsys.readouterr().err

    def test_diretorio_inexistente_retorna_erro_legivel(self, tmp_path: Path, capsys):
        codigo = main([
            "run",
            "-i", str(tmp_path / "inexistente"),
            "-o", str(tmp_path / "processed"),
            "--sem-legado",
        ])

        assert codigo == 1
        assert "Diretório não encontrado" in capsys.readouterr().err

    def test_resumo_mostra_kpis(self, projeto: Path, capsys):
        main(["run", "-i", str(projeto / "raw"), "-o", str(projeto / "processed")])
        saida = capsys.readouterr().out
        assert "Faturamento" in saida
        assert "Ticket médio" in saida
        assert "Validação" in saida

    def test_publica_validos_e_envia_recusados_para_quarentena(
        self, projeto: Path, capsys
    ):
        import openpyxl
        import pandas as pd

        origem = projeto / "raw" / "vendas_sinteticas.xlsx"
        wb = openpyxl.load_workbook(origem)
        ws = wb.active
        assert ws is not None
        for row in ws.iter_rows():
            if row[0].value and row[9].value and isinstance(row[13].value, (int, float)):
                row[9].value = None
                break
        wb.save(origem)

        codigo = main([
            "run",
            "-i", str(projeto / "raw"),
            "-o", str(projeto / "processed"),
            "--quarantine", str(projeto / "quarantine"),
        ])

        assert codigo == 2
        publicado = pd.read_parquet(projeto / "processed" / "vendas_consolidadas.parquet")
        assert (publicado["numero_documento"].str.strip() != "").all()
        quarentenas = list((projeto / "quarantine").rglob("registros_rejeitados.parquet"))
        assert len(quarentenas) == 1
        assert len(pd.read_parquet(quarentenas[0])) == 1
        auditoria = json.loads(
            (projeto / "processed" / "execucao.json").read_text(encoding="utf-8")
        )
        assert auditoria["status"] == "PARCIAL"
        assert any(
            saida["arquivo"] == "registros_rejeitados.parquet"
            for saida in auditoria["saidas"]
        )


class TestQuery:
    def test_lista_consultas(self, capsys):
        assert main(["query", "--listar"]) == 0
        assert "sazonalidade" in capsys.readouterr().out

    def test_consulta_o_parquet_publicado(self, projeto: Path, capsys):
        main(["run", "-i", str(projeto / "raw"), "-o", str(projeto / "processed")])
        capsys.readouterr()
        codigo = main([
            "query", "SELECT COUNT(*) AS n FROM vendas",
            "--parquet", str(projeto / "processed" / "vendas_consolidadas.parquet"),
        ])
        assert codigo == 0
        assert "n" in capsys.readouterr().out

    def test_saida_em_csv(self, projeto: Path, capsys):
        main(["run", "-i", str(projeto / "raw"), "-o", str(projeto / "processed")])
        capsys.readouterr()
        main([
            "query", "cobertura", "--csv",
            "--parquet", str(projeto / "processed" / "vendas_consolidadas.parquet"),
        ])
        assert "notas" in capsys.readouterr().out

    def test_parquet_ausente_falha_com_orientacao(self, tmp_path: Path, capsys):
        codigo = main([
            "query", "SELECT 1", "--parquet", str(tmp_path / "nao_existe.parquet"),
        ])
        assert codigo == 1
        assert "aldebaran run" in capsys.readouterr().err

    def test_sem_consulta_retorna_erro_de_uso(self, capsys):
        assert main(["query"]) == 2


class TestDashboard:
    def test_gera_visao_executiva_do_parquet(self, projeto: Path, capsys):
        main(["run", "-i", str(projeto / "raw"), "-o", str(projeto / "processed")])

        codigo = main([
            "dashboard",
            "--parquet", str(projeto / "processed" / "vendas_consolidadas.parquet"),
            "--output", str(projeto / "dashboard.html"),
        ])

        assert codigo == 0
        assert (projeto / "dashboard.html").exists()

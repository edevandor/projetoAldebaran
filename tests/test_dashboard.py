from analytics.dashboard import build_dashboard
from pipeline import run_pipeline


def test_dashboard_deriva_metricas_do_parquet(tmp_path):
    run_pipeline("tests/fixtures", output_dir=tmp_path / "processed", legado_dir=None)

    destino = build_dashboard(
        tmp_path / "processed" / "vendas_consolidadas.parquet",
        tmp_path / "dashboard.html",
    )
    conteudo = destino.read_text(encoding="utf-8")

    assert "Visão executiva" in conteudo
    assert "Faturamento" in conteudo
    assert "sistema_origem" in conteudo
    assert '"id_venda"' not in conteudo
    assert "cdn" not in conteudo.lower()

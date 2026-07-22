"""Interface de linha de comando do Aldebaran.

Três verbos cobrem o ciclo completo:

    aldebaran demo    gera dados sintéticos nos formatos de origem
    aldebaran run     executa o pipeline e publica o Parquet
    aldebaran query   consulta o Parquet publicado, em SQL
"""

import argparse
import sys
from decimal import Decimal
from pathlib import Path

from analytics.dashboard import build_dashboard
from demo.gerador_rel import gerar_todos as gerar_rel_todos
from demo.gerador_xlsx import gerar_xlsx
from pipeline import PipelineContractError, run_pipeline
from query.engine import PARQUET_PADRAO, consultar, listar_consultas


def _formatar_centavos(valor: int) -> str:
    texto = f"{Decimal(valor) / Decimal(100):,.2f}"
    return "R$ " + texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def comando_demo(args: argparse.Namespace) -> int:
    """Gera os arquivos de demonstração."""
    xlsx = gerar_xlsx(Path(args.raw_dir) / "vendas_sinteticas.xlsx", seed=args.seed)
    print(f"XLSX (formato atual)   {xlsx}")

    if not args.sem_legado:
        for nome, caminho in gerar_rel_todos(Path(args.legado_dir), seed=args.seed).items():
            print(f".rel {nome:<18} {caminho}")

    print("\nExecute o pipeline com: aldebaran run")
    return 0


def comando_run(args: argparse.Namespace) -> int:
    """Executa o pipeline e imprime o resumo da execução."""
    try:
        resultado = run_pipeline(
            data_dir=args.input,
            output_dir=args.output,
            csv_path=args.csv_path,
            exportar_csv=args.csv,
            legado_dir=None if args.sem_legado else args.legado,
            quarantine_dir=args.quarantine,
        )
    except (PipelineContractError, NotADirectoryError) as exc:
        print(f"Contrato inválido: {exc}", file=sys.stderr)
        return 1

    kpis = resultado["kpis"]
    validacao = resultado["validacao"]

    print(resultado["auditoria"].resumo())
    print()
    for etapa, metricas in resultado["etapas"].items():
        detalhes = ", ".join(f"{k}={v}" for k, v in metricas.items() if k != "duracao_s")
        print(f"  {etapa:<14} {metricas.get('duracao_s', 0):>6.2f}s  {detalhes}")

    print()
    print(f"  Faturamento    {_formatar_centavos(kpis['total_faturamento_centavos'])}")
    print(f"  Notas fiscais  {kpis['qtd_notas_fiscais']:,}".replace(",", "."))
    print(f"  Itens          {kpis['total_itens']:,}".replace(",", "."))
    print(f"  Ticket médio   {_formatar_centavos(kpis['ticket_medio_centavos'])}")
    legado = resultado.get("legado") or {}
    if legado.get("ingeridos") or legado.get("ignorados"):
        print()
        for item in legado.get("ingeridos", []):
            print(f"  legado: {item['arquivo']} — {item['linhas']} linhas")
        for item in legado.get("ignorados", []):
            print(f"  legado: {item['arquivo']} — ignorado ({item['motivo']})")

    print()
    print(f"  Validação: {validacao.summary()}")

    return 2 if resultado["status"] == "PARCIAL" else 0


def comando_query(args: argparse.Namespace) -> int:
    """Executa uma consulta SQL sobre o Parquet publicado."""
    if args.listar:
        print("Consultas disponíveis:")
        for nome in listar_consultas():
            print(f"  {nome}")
        return 0

    if not args.sql:
        print("Informe uma consulta SQL ou o nome de uma consulta (--listar).",
              file=sys.stderr)
        return 2

    try:
        resultado = consultar(args.sql, parquet_path=args.parquet)
    except (FileNotFoundError, ImportError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.csv:
        resultado.to_csv(sys.stdout, index=False)
    else:
        print(resultado.to_string(index=False))
    return 0


def comando_dashboard(args: argparse.Namespace) -> int:
    """Gera a visão executiva local a partir do Parquet publicado."""
    try:
        destino = build_dashboard(args.parquet, args.output)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Dashboard gerado em {destino}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aldebaran",
        description="Pipeline de consolidação de histórico comercial de ERP legado.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_demo = sub.add_parser("demo", help="gera dados sintéticos nos formatos de origem")
    p_demo.add_argument("--raw-dir", default="data/raw", help="destino do XLSX")
    p_demo.add_argument("--legado-dir", default="data/legado", help="destino dos .rel")
    p_demo.add_argument("--sem-legado", action="store_true", help="não gerar os .rel")
    p_demo.add_argument("--seed", type=int, default=42, help="semente do gerador")
    p_demo.set_defaults(func=comando_demo)

    p_run = sub.add_parser("run", help="executa o pipeline e publica o Parquet")
    p_run.add_argument("-i", "--input", default="data/raw", help="diretório de origem")
    p_run.add_argument(
        "-o",
        "--output",
        default="data/processed",
        help="diretório de publicação (Parquet, auditoria e artefatos opcionais)",
    )
    p_run.add_argument("-l", "--legado", default="data/legado",
                       help="diretório com os .rel do ERP legado")
    p_run.add_argument("--sem-legado", action="store_true",
                       help="publicar apenas o histórico do sistema atual")
    p_run.add_argument("--csv", action="store_true", help="exportar também CSV para BI")
    p_run.add_argument("--csv-path", default=None, help="caminho do CSV")
    p_run.add_argument("--quarantine", default=None, help="diretório dos registros rejeitados")
    p_run.set_defaults(func=comando_run)

    p_query = sub.add_parser("query", help="consulta o Parquet publicado em SQL")
    p_query.add_argument("sql", nargs="?", help="SQL ou nome de consulta pronta")
    p_query.add_argument("--parquet", default=str(PARQUET_PADRAO), help="Parquet a consultar")
    p_query.add_argument("--listar", action="store_true", help="lista as consultas prontas")
    p_query.add_argument("--csv", action="store_true", help="saída em CSV")
    p_query.set_defaults(func=comando_query)

    p_dashboard = sub.add_parser(
        "dashboard",
        help="gera uma visão executiva HTML a partir do Parquet",
    )
    p_dashboard.add_argument("--parquet", default=str(PARQUET_PADRAO))
    p_dashboard.add_argument("-o", "--output", default="data/processed/dashboard.html")
    p_dashboard.set_defaults(func=comando_dashboard)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

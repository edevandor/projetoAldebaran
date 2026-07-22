"""Geração de arquivos .rel sintéticos no formato do ERP legado.

O ERP anterior (2002–2022) exportava relatórios de impressão: texto de
largura fixa em 132 colunas, com cabeçalhos de página repetidos a cada
bloco e números no formato brasileiro. Estes geradores reproduzem esse
layout — incluindo as anomalias que o pipeline precisa de tratar:

  - anos com 2 dígitos, que regridem dentro do arquivo;
  - datas de compra substituídas por uma sentinela quando o sistema não
    tinha a data real;
  - o CI (Controlo Interno) como único eixo cronológico confiável.
"""

import random
from pathlib import Path

from demo.catalogo import PRODUTOS, SEMENTE_PADRAO, UNIDADES

LARGURA = 132
SENTINELA_DATA = "01/01/19"
LINHAS_POR_PAGINA = 40


def _fmt_br(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro: 1.234,56."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _cabecalho_pagina(titulo: str, pagina: int, periodo: str) -> list[str]:
    """Cabeçalho de página do relatório, ignorado pelos parsers."""
    return [
        "=" * LARGURA,
        f"01-EMPRESA DEMONSTRACAO LTDA{'':>40}Pagina: {pagina:>4}".ljust(LARGURA),
        f"SISTEMA INTEGRADO - {titulo}".ljust(LARGURA),
        f"Mapa Estatistico   Periodo: {periodo}".ljust(LARGURA),
        "Almox..: 01 - ALMOXARIFADO CENTRAL".ljust(LARGURA),
        "-" * LARGURA,
    ]


def _escrever(destino: Path, linhas: list[str]) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(linhas) + "\n", encoding="latin-1")
    return destino


def gerar_rel_sintetico(
    destino: Path,
    num_itens: int = 60,
    seed: int = SEMENTE_PADRAO,
) -> Path:
    """Gera um .rel sintético: totais acumulados por item, sem venda individual.

    É o relatório que o ERP legado produzia por período — agregado, sem
    data, nota fiscal ou vendedor.
    """
    rng = random.Random(seed)
    linhas: list[str] = []
    pagina = 1
    linhas += _cabecalho_pagina("MODULO DE VENDAS", pagina, "01/01/2002 a 31/12/2022")
    linhas.append("Item  Artigo".ljust(LARGURA))

    for i in range(num_itens):
        if i and i % LINHAS_POR_PAGINA == 0:
            pagina += 1
            linhas += _cabecalho_pagina(
                "MODULO DE VENDAS", pagina, "01/01/2002 a 31/12/2022"
            )
            linhas.append("Item  Artigo".ljust(LARGURA))

        codigo, descricao = PRODUTOS[i % len(PRODUTOS)]
        quantidade = round(rng.uniform(1, 900), 2)
        custo = round(quantidade * rng.uniform(20, 900), 2)
        compra = round(custo * rng.uniform(1.2, 2.4), 2)
        liquido = round(compra * 0.94, 2)
        margem = round((compra - custo) / compra * 100, 2)

        linhas.append(
            f"{codigo:>6}"
            f"{descricao[:48]:<48}"
            f"{_fmt_br(rng.uniform(0, 99), 0):>9}"
            f"{rng.choice(UNIDADES):<4}"
            f"{_fmt_br(quantidade):>17}"
            f"{_fmt_br(custo):>13}"
            f"{_fmt_br(compra):>13}"
            f"{_fmt_br(liquido):>12}"
            f"{_fmt_br(margem) + '%':>10}"
        )

    linhas.append("    Total Geral".ljust(LARGURA))
    return _escrever(destino, linhas)


def gerar_rel_analitico_com_gabarito(
    destino: Path,
    num_vendas: int = 120,
    ano_inicial: int = 2002,
    ano_final: int = 2022,
    seed: int = SEMENTE_PADRAO,
    proporcao_ano_regredido: float = 0.15,
) -> tuple[Path, dict[int, int]]:
    """Gera um .rel analítico e o gabarito dos anos reais.

    O ano é impresso com 2 dígitos e o CI cresce monotonicamente ao longo
    de todo o período — é essa sequência que permite reconstruir a
    cronologia que a data impressa, sozinha, não resolve.

    O gabarito mapeia cada CI ao ano em que a venda realmente ocorreu.
    Sem ele, só é possível testar propriedades que o algoritmo garante por
    construção; com ele, dá para verificar se a reconstrução acertou.

    `proporcao_ano_regredido` reproduz a anomalia que motivou o algoritmo:
    parte das linhas sai com o ano impresso de um exercício anterior,
    enquanto o CI continua crescendo. Sem esse ruído, o arquivo sintético
    não exercita a desambiguação e qualquer teste sobre ele passaria mesmo
    com o algoritmo desligado.

    Returns:
        Tupla (caminho do arquivo, {ci: ano_real}).
    """
    rng = random.Random(seed)
    linhas: list[str] = []
    pagina = 1
    periodo = f"01/01/{ano_inicial} a 31/12/{ano_final}"
    linhas += _cabecalho_pagina("MODULO DE VENDAS", pagina, periodo)
    linhas.append("Item  Artigo".ljust(LARGURA))

    ci = 10005
    contador = 0
    anos = list(range(ano_inicial, ano_final + 1))
    gabarito: dict[int, int] = {}

    for indice, ano in enumerate(anos):
        vendas_no_ano = max(1, num_vendas // len(anos))
        for sequencia in range(vendas_no_ano):
            ci += rng.randint(1, 9)
            gabarito[ci] = ano
            mes = rng.randint(1, 12)
            dia = rng.randint(1, 28)

            # O ano impresso nem sempre acompanha o ano real. A primeira
            # venda de cada ano fica intacta: é ela que ancora a correção.
            ano_impresso = ano
            if sequencia > 0 and rng.random() < proporcao_ano_regredido:
                ano_impresso = max(ano_inicial, ano - rng.randint(1, 3))
            # Uma venda tem de 1 a 4 itens — a granularidade do relatório
            # é o item, não a nota.
            for _ in range(rng.randint(1, 4)):
                if contador and contador % LINHAS_POR_PAGINA == 0:
                    pagina += 1
                    linhas += _cabecalho_pagina("MODULO DE VENDAS", pagina, periodo)
                    linhas.append("Item  Artigo".ljust(LARGURA))
                contador += 1

                codigo, descricao = PRODUTOS[rng.randrange(len(PRODUTOS))]
                quantidade = round(rng.uniform(1, 12), 2)
                total = round(quantidade * rng.uniform(15, 800), 2)

                linhas.append(
                    f"{codigo:>6}"
                    f"{descricao[:60]:<60}"
                    f"{_fmt_br(rng.uniform(0, 99), 0):>5}"
                    f"{rng.choice(UNIDADES):<3}"
                    f"{'':6}"
                    f"{_fmt_br(quantidade):>12}"
                    f"{f'{dia:02d}/{mes:02d}/{ano_impresso % 100:02d}':>10}"
                    f"{ci:>14}"
                    f"{_fmt_br(total):>16}"
                )
        if indice % 5 == 0:
            linhas.append("    Total Movto do Periodo".ljust(LARGURA))

    linhas.append("    Total Geral".ljust(LARGURA))
    return _escrever(destino, linhas), gabarito


def gerar_rel_analitico(
    destino: Path,
    num_vendas: int = 120,
    ano_inicial: int = 2002,
    ano_final: int = 2022,
    seed: int = SEMENTE_PADRAO,
) -> Path:
    """Gera um .rel analítico sintético."""
    caminho, _ = gerar_rel_analitico_com_gabarito(
        destino, num_vendas=num_vendas, ano_inicial=ano_inicial,
        ano_final=ano_final, seed=seed,
    )
    return caminho


def gerar_rel_compras(
    destino: Path,
    num_entradas: int = 90,
    seed: int = SEMENTE_PADRAO,
    proporcao_sentinela: float = 0.35,
) -> Path:
    """Gera um .rel de compras com datas corrompidas.

    Reproduz o defeito do legado: parte das entradas perdeu a data real e
    recebeu a sentinela `01/01/19`, e o ano impresso não acompanha o
    período. Só o CI permanece cronologicamente confiável — é o que o parser
    de compras usa para reconstruir o ano.
    """
    rng = random.Random(seed)
    linhas: list[str] = []
    pagina = 1
    periodo = "01/01/2005 a 31/12/2022"
    linhas += _cabecalho_pagina("MODULO DE COMPRAS", pagina, periodo)
    linhas.append("Item   Artigo".ljust(LARGURA))

    ci = 10005
    contador = 0

    for _ in range(num_entradas):
        ci += rng.randint(20, 140)
        if rng.random() < proporcao_sentinela:
            data_impressa = SENTINELA_DATA
        else:
            # Ano impresso "20" — incorreto para a maioria dos registros.
            data_impressa = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/20"

        for _ in range(rng.randint(1, 5)):
            if contador and contador % LINHAS_POR_PAGINA == 0:
                pagina += 1
                linhas += _cabecalho_pagina("MODULO DE COMPRAS", pagina, periodo)
                linhas.append("Item   Artigo".ljust(LARGURA))
            contador += 1

            codigo, descricao = PRODUTOS[rng.randrange(len(PRODUTOS))]
            quantidade = round(rng.uniform(1, 120), 2)
            total = round(quantidade * rng.uniform(30, 1500), 2)

            linhas.append(
                f"{codigo:>6}"
                f"{descricao[:60]:<60}"
                f"{_fmt_br(rng.uniform(0, 99), 0):>5}"
                f"{rng.choice(UNIDADES):<3}"
                f"{'':6}"
                f"{_fmt_br(quantidade):>12}"
                f"{data_impressa:>10}"
                f"{ci:>14}"
                f"{_fmt_br(total):>16}"
            )

    linhas.append("    Total Geral".ljust(LARGURA))
    return _escrever(destino, linhas)


def gerar_todos(
    diretorio: Path = Path("data/legado"),
    seed: int = SEMENTE_PADRAO,
) -> dict[str, Path]:
    """Gera os três arquivos .rel de demonstração."""
    diretorio = Path(diretorio)
    return {
        "sintetico": gerar_rel_sintetico(diretorio / "vendas_sintetico.rel", seed=seed),
        "analitico": gerar_rel_analitico(diretorio / "vendas_analitico.rel", seed=seed),
        "compras": gerar_rel_compras(diretorio / "compras_analitico.rel", seed=seed),
    }

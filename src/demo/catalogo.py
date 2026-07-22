"""Catálogo partilhado pelos geradores de dados sintéticos."""

PRODUTOS: list[tuple[str, str]] = [
    ("000101", "PRODUTO ALFA MODELO 100"),
    ("000102", "PRODUTO ALFA MODELO 200"),
    ("000103", "PRODUTO ALFA MODELO 300"),
    ("000204", "COMPONENTE BETA TAMANHO P"),
    ("000205", "COMPONENTE BETA TAMANHO G"),
    ("000306", "CONSUMIVEL GAMA TIPO 1"),
    ("000307", "CONSUMIVEL GAMA TIPO 2"),
    ("000408", "EQUIPAMENTO DELTA BASICO"),
    ("000409", "EQUIPAMENTO DELTA AVANCADO"),
    ("000510", "KIT EPSILON PADRAO"),
    ("000611", "ACESSORIO ZETA MODELO 10"),
    ("000612", "ACESSORIO ZETA MODELO 20"),
    ("000713", "INSUMO ETA UNIDADE"),
    ("000714", "INSUMO ETA FARDO"),
    ("000815", "SERVICO COMPLEMENTAR PADRAO"),
]

RESPONSAVEIS: list[str] = ["Responsavel A", "Responsavel B", "Responsavel C"]

ARTIGOS: list[str] = ["Venda Direta", "Orcamento", "Reposicao"]

UNIDADES: list[str] = ["UN", "PC", "M", "KG"]

SEMENTE_PADRAO = 42

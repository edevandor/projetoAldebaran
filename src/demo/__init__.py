"""Geração de dados sintéticos que reproduzem os formatos de origem.

Os dados reais do ERP não podem ser versionados. Estes geradores
produzem arquivos com a **mesma estrutura** — hierarquia do XLSX,
largura fixa do .rel, datas corrompidas do legado — para que o pipeline
seja executável e verificável por qualquer pessoa.
"""

from demo.gerador_rel import gerar_rel_analitico, gerar_rel_compras, gerar_rel_sintetico
from demo.gerador_xlsx import gerar_xlsx

__all__ = [
    "gerar_xlsx",
    "gerar_rel_sintetico",
    "gerar_rel_analitico",
    "gerar_rel_compras",
]

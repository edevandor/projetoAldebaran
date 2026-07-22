"""Gera os dados sintéticos de demonstração.

Equivalente a `aldebaran demo`. Mantido para execução direta, sem
instalação do pacote:

    PYTHONPATH=src python scripts/gerar_dados_sinteticos.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["demo"]))

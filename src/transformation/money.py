"""Conversão monetária exata para a unidade canônica em centavos."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVO = Decimal("0.01")


def to_centavos(valor: object) -> int:
    """Converte um valor monetário para centavos inteiros."""
    texto = str(valor).strip()
    if not texto:
        raise ValueError("Valor monetário vazio")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        decimal = Decimal(texto).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {valor}") from exc
    return int(decimal * 100)

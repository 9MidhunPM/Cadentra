from decimal import ROUND_HALF_UP, Context, Decimal, InvalidOperation, localcontext

CENT = Decimal("0.01")


def money(value: Decimal | str) -> Decimal:
    if not isinstance(value, (Decimal, str)):
        raise ValueError("Money must be Decimal or a decimal string")
    try:
        amount = Decimal(value)
        if not amount.is_finite():
            raise ValueError("Money must be finite")
        with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
            return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Invalid monetary value") from exc


def money_string(value: Decimal | str) -> str:
    return format(money(value), ".2f")

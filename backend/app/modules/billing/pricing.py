"""Pure invoice arithmetic for immutable, already-priced subscription lines.

Callers supply exactly one base-fee line and product unit prices with variant
adjustments already applied. Eligibility, rule selection and usage reservation
belong to the transactional billing service, not this calculator.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("9999999999999999.99")


def _nonnegative_decimal(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative Decimal")


def _money(value: Decimal) -> Decimal:
    if value > MAX_MONEY:
        raise ValueError("Invoice amount exceeds NUMERIC(18,2) storage")
    if not value:
        return ZERO
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class PricingLine:
    stable_line_key: str
    quantity: int
    unit_price: Decimal
    tax_rates: tuple[Decimal, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.stable_line_key, str) or not self.stable_line_key.strip():
            raise ValueError("Line key must be a nonempty string")
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        _nonnegative_decimal(self.unit_price, "Unit price")
        with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
            if self.unit_price > MAX_MONEY or self.unit_price != self.unit_price.quantize(CENT):
                raise ValueError("Unit price must fit NUMERIC(18,2)")
        if not isinstance(self.tax_rates, tuple):
            raise ValueError("Tax rates must be an immutable tuple")
        for rate in self.tax_rates:
            _nonnegative_decimal(rate, "Tax rate")
            if rate > 100:
                raise ValueError("Tax rate must be at most 100 percent")


@dataclass(frozen=True, slots=True)
class SelectedDiscount:
    kind: str
    value: Decimal
    eligible_line_keys: frozenset[str]

    def __post_init__(self) -> None:
        if self.kind not in ("FIXED", "PERCENT"):
            raise ValueError("Discount kind must be FIXED or PERCENT")
        _nonnegative_decimal(self.value, "Discount value")
        if self.kind == "PERCENT" and self.value > 100:
            raise ValueError("Percentage discount must be at most 100")
        if not isinstance(self.eligible_line_keys, frozenset) or any(
            not isinstance(key, str) or not key.strip() for key in self.eligible_line_keys
        ):
            raise ValueError("Eligible line keys must be an immutable set of nonempty strings")


@dataclass(frozen=True, slots=True)
class LineCalculation:
    line: PricingLine
    gross: Decimal
    discount: Decimal
    taxable_amount: Decimal
    tax_amounts: tuple[Decimal, ...]
    tax_total: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceCalculation:
    lines: tuple[LineCalculation, ...]
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal


def _allocate_discount(
    lines: tuple[PricingLine, ...], gross: tuple[Decimal, ...], rule: SelectedDiscount | None,
) -> tuple[Decimal, ...]:
    allocations = [ZERO for _ in lines]
    if rule is None:
        return tuple(allocations)
    eligible = [index for index, line in enumerate(lines)
                if line.stable_line_key in rule.eligible_line_keys]
    eligible_gross = sum((gross[index] for index in eligible), ZERO)
    if not eligible_gross:
        return tuple(allocations)
    requested = (eligible_gross * rule.value / 100 if rule.kind == "PERCENT" else rule.value)
    target = _money(min(requested, eligible_gross))
    shares = {index: target * gross[index] / eligible_gross for index in eligible}
    for index in eligible:
        allocations[index] = shares[index].quantize(CENT, rounding=ROUND_DOWN)
    cents_remaining = int((target - sum(allocations, ZERO)) / CENT)
    order = sorted(eligible, key=lambda index: (
        -(shares[index] - allocations[index]), lines[index].stable_line_key,
    ))
    for index in order[:cents_remaining]:
        allocations[index] += CENT
    return tuple(allocations)


def calculate_invoice(
    lines: tuple[PricingLine, ...], discount: SelectedDiscount | None = None,
) -> InvoiceCalculation:
    """Calculate cents without mutation, persistence, floats or ambient rounding."""
    if not isinstance(lines, tuple) or not lines or any(
        not isinstance(line, PricingLine) for line in lines
    ):
        raise ValueError("Lines must be a nonempty tuple of PricingLine values")
    keys = {line.stable_line_key for line in lines}
    if len(keys) != len(lines):
        raise ValueError("Line keys must be unique")
    if discount is not None and (
        not isinstance(discount, SelectedDiscount) or not discount.eligible_line_keys <= keys
    ):
        raise ValueError("Selected discount must reference existing line keys")

    # Isolate precision and rounding from the caller's Decimal context. Fifty
    # digits cover NUMERIC(18,2) intermediates and proportional cent allocation.
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        gross = tuple(_money(line.unit_price * line.quantity) for line in lines)
        subtotal = _money(sum(gross, ZERO))
        allocations = _allocate_discount(lines, gross, discount)
        calculated = []
        for line, line_gross, line_discount in zip(lines, gross, allocations):
            taxable = _money(line_gross - line_discount)
            taxes = tuple(_money(taxable * rate / 100) for rate in line.tax_rates)
            tax_total = _money(sum(taxes, ZERO))
            calculated.append(LineCalculation(
                line=line, gross=line_gross, discount=line_discount,
                taxable_amount=taxable, tax_amounts=taxes, tax_total=tax_total,
                total=_money(taxable + tax_total),
            ))
        return InvoiceCalculation(
            lines=tuple(calculated), subtotal=subtotal,
            discount_total=_money(sum(allocations, ZERO)),
            tax_total=_money(sum((line.tax_total for line in calculated), ZERO)),
            total=_money(sum((line.total for line in calculated), ZERO)),
        )

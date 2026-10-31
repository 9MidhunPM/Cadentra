"""Catalog inputs require decimal strings, never binary floating point money."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints


def decimal_string(value):
    if not isinstance(value, str):
        raise ValueError("Supply money as a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not parsed.is_finite() or parsed.as_tuple().exponent < -2:
        raise ValueError("Use a finite amount with at most two decimal places")
    return parsed


Amount = Annotated[Decimal, BeforeValidator(decimal_string), Field(max_digits=18, decimal_places=2)]
Nonnegative = Annotated[
    Decimal, BeforeValidator(decimal_string), Field(ge=0, max_digits=18, decimal_places=2)
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Cadence = Literal["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductWrite(Input):
    name: Name
    product_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
    ]
    sales_price: Nonnegative
    cost_price: Nonnegative
    notes: str | None = Field(default=None, max_length=10000)
    active: bool = True


class ProductPatch(Input):
    name: Name | None = None
    product_type: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
    ) = None
    sales_price: Nonnegative | None = None
    cost_price: Nonnegative | None = None
    notes: str | None = Field(default=None, max_length=10000)
    active: bool | None = None


class VariantWrite(Input):
    attribute_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    attribute_value: Name
    price_delta: Amount
    active: bool = True


class VariantPatch(Input):
    attribute_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
        | None
    ) = None
    attribute_value: Name | None = None
    price_delta: Amount | None = None
    active: bool | None = None


class PlanWrite(Input):
    name: Name
    base_fee: Nonnegative
    currency: Literal["INR"]
    cadence: Cadence
    min_quantity: int = Field(ge=1, strict=True)
    available_from: date
    available_until: date | None = None
    allow_pause: bool
    allow_early_close: bool
    allow_renew: bool
    auto_close: bool
    tax_rule_ids: list[UUID] = Field(default_factory=list, max_length=100)


class PlanPatch(Input):
    name: Name | None = None
    base_fee: Nonnegative | None = None
    currency: Literal["INR"] | None = None
    cadence: Cadence | None = None
    min_quantity: int | None = Field(default=None, ge=1, strict=True)
    available_from: date | None = None
    available_until: date | None = None
    allow_pause: bool | None = None
    allow_early_close: bool | None = None
    allow_renew: bool | None = None
    auto_close: bool | None = None
    tax_rule_ids: list[UUID] | None = Field(default=None, max_length=100)

"""Strict rule inputs; financial values arrive as decimal strings."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def decimal_text(value):
    if not isinstance(value, str):
        raise ValueError("Supply a decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid decimal") from error
    if not result.is_finite():
        raise ValueError("Decimal must be finite")
    return result


Money = Annotated[
    Decimal, BeforeValidator(decimal_text), Field(ge=0, max_digits=18, decimal_places=2)
]
Rate = Annotated[
    Decimal, BeforeValidator(decimal_text), Field(ge=0, le=100, max_digits=9, decimal_places=4)
]
Value = Annotated[
    Decimal, BeforeValidator(decimal_text), Field(ge=0, max_digits=20, decimal_places=4)
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxWrite(Input):
    name: Name
    rate_percent: Rate
    valid_from: date
    valid_until: date | None = None
    product_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    active: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def window(self):
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("Tax validity end must follow its start")
        if len(set(self.product_ids)) != len(self.product_ids):
            raise ValueError("Product IDs must be unique")
        return self


class TaxPatch(Input):
    effective_from: date
    name: Name | None = None
    rate_percent: Rate | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    product_ids: list[UUID] | None = Field(default=None, max_length=1000)
    active: bool | None = Field(default=None, strict=True)


class DiscountWrite(Input):
    name: Name
    kind: Literal["FIXED", "PERCENT"]
    value: Value
    scope: Literal["SUBSCRIPTION", "PRODUCTS"]
    product_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    min_purchase: Money = Decimal("0.00")
    min_quantity: int = Field(default=0, ge=0, le=2147483647, strict=True)
    starts_on: date
    ends_on: date | None = None
    usage_limit: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    active: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def policy(self):
        if self.ends_on is not None and self.ends_on <= self.starts_on:
            raise ValueError("Discount validity end must follow its start")
        if self.kind == "PERCENT" and self.value > 100:
            raise ValueError("Percentage must not exceed 100")
        if self.kind == "FIXED" and (
            self.value != self.value.quantize(Decimal("0.01"))
            or self.value > Decimal("9999999999999999.99")
        ):
            raise ValueError("Fixed value must fit money precision")
        if len(set(self.product_ids)) != len(self.product_ids):
            raise ValueError("Product IDs must be unique")
        if self.scope == "PRODUCTS" and not self.product_ids:
            raise ValueError("Product scope requires at least one product")
        if self.scope == "SUBSCRIPTION" and self.product_ids:
            raise ValueError("Subscription scope does not use product IDs")
        return self


class DiscountPatch(Input):
    effective_from: date
    name: Name | None = None
    kind: Literal["FIXED", "PERCENT"] | None = None
    value: Value | None = None
    scope: Literal["SUBSCRIPTION", "PRODUCTS"] | None = None
    product_ids: list[UUID] | None = Field(default=None, max_length=1000)
    min_purchase: Money | None = None
    min_quantity: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    starts_on: date | None = None
    ends_on: date | None = None
    usage_limit: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    active: bool | None = Field(default=None, strict=True)

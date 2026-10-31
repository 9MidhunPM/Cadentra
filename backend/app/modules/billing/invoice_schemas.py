"""Strict financial mutation inputs; totals are always server-owned."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints


def payment_amount(value):
    if not isinstance(value, str):
        raise ValueError("Supply an amount as a decimal string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not amount.is_finite() or amount.as_tuple().exponent < -2:
        raise ValueError("Use a finite amount with at most two fractional digits")
    return amount


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


RequestKey = Annotated[str, StringConstraints(min_length=1, max_length=128, strip_whitespace=True)]


class PaymentWrite(Input):
    method: Literal["MANUAL", "BANK_TRANSFER", "UPI", "CASH", "CARD_EXTERNAL", "OTHER"]
    amount: Annotated[
        Decimal, BeforeValidator(payment_amount), Field(gt=0, max_digits=18, decimal_places=2)
    ]
    paid_on: date
    note: str = Field(max_length=10000)
    external_reference: str | None = Field(default=None, max_length=200)
    request_key: RequestKey


class CancelInvoice(Input):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class SendInvoice(Input):
    request_key: RequestKey

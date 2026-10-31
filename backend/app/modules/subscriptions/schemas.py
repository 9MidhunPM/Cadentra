"""Subscription requests preserve omitted fields and reject authoritative totals."""

from datetime import date
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def service_date(value):
    if type(value) is date:
        return value
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Use a service date in YYYY-MM-DD format")
    return date.fromisoformat(value)


ServiceDate = Annotated[date, BeforeValidator(service_date)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Quantity = Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]
Terms = Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for name in self.model_fields_set - self.nullable_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TemplateLine(Input):
    nullable_fields = frozenset({"variant_id"})
    product_id: UUID
    variant_id: UUID | None = None
    quantity: Quantity


class TemplateWrite(Input):
    name: Name
    plan_id: UUID
    valid_days: Quantity
    lines: list[TemplateLine] = Field(max_length=100)


class TemplatePatch(Input):
    name: Name | None = None
    plan_id: UUID | None = None
    valid_days: Quantity | None = None
    lines: list[TemplateLine] | None = Field(default=None, max_length=100)


class SubscriptionCreate(Input):
    nullable_fields = frozenset({"template_id"})
    customer_id: UUID
    plan_id: UUID
    template_id: UUID | None = None
    start_date: ServiceDate
    end_date: ServiceDate
    payment_terms_days: Terms
    lines: list[TemplateLine] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_creation(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if "lines" not in self.model_fields_set and self.template_id is None:
            raise ValueError("lines are required without a template")
        return self


class SubscriptionEdit(Input):
    start_date: ServiceDate | None = None
    end_date: ServiceDate | None = None
    payment_terms_days: Terms | None = None
    lines: list[TemplateLine] | None = Field(default=None, max_length=100)


class QuoteIssue(Input):
    valid_days: Quantity


class LifecycleAction(Input):
    nullable_fields = frozenset({"reason"})
    reason: str | None = Field(default=None, max_length=2000)


class Renew(Input):
    start_date: ServiceDate
    end_date: ServiceDate
    payment_terms_days: Terms | None = None

    @model_validator(mode="after")
    def validate_term(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

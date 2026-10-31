"""Deterministic fictional inputs for the explicitly invoked commerce demo.

Only product descriptions/codes come from the attributed catalog manifest.
Customer identities, INR prices, variants and commercial terms are synthetic.
Functions return new dictionaries; callers own validation and persistence.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TypedDict
from uuid import NAMESPACE_URL, UUID, uuid5

from app.core.demo_contacts import DEMO_CONTACT_DOMAIN
from app.core.money import money

PROFILE_VERSION = 1
PROFILE_NAMESPACE = uuid5(NAMESPACE_URL, "https://cadentra.example.invalid/commerce-demo/v1")
CUSTOMER_COUNT = 96
CATALOG_COUNT = 80

__all__ = [
    "CATALOG_COUNT",
    "CUSTOMER_COUNT",
    "PROFILE_NAMESPACE",
    "PROFILE_VERSION",
    "catalog",
    "customers",
    "plans",
    "record_id",
    "templates",
]


class CustomerSpec(TypedDict):
    id: UUID
    display_name: str
    company_name: str
    email: str
    billing_address: dict[str, str]


class VariantSpec(TypedDict):
    id: UUID
    product_id: UUID
    attribute_name: str
    attribute_value: str
    price_delta: Decimal
    active: bool


class ProductSpec(TypedDict):
    id: UUID
    stock_code: str
    original_description: str
    name: str
    product_type: str
    sales_price: Decimal
    cost_price: Decimal
    notes: str
    active: bool
    variants: list[VariantSpec]


class PlanSpec(TypedDict):
    id: UUID
    name: str
    base_fee: Decimal
    currency: str
    cadence: str
    min_quantity: int
    available_from: date
    available_until: date | None
    allow_pause: bool
    allow_early_close: bool
    allow_renew: bool
    auto_close: bool


class TemplateLineSpec(TypedDict):
    id: UUID
    product_id: UUID
    variant_id: UUID | None
    quantity: int


class TemplateSpec(TypedDict):
    id: UUID
    name: str
    plan_id: UUID
    valid_days: int
    active: bool
    lines: list[TemplateLineSpec]


def record_id(kind: str, key: str | int) -> UUID:
    """Stable identity within the versioned demo cohort, never an existing row."""
    if not kind or ":" in kind:
        raise ValueError("A nonempty demo record kind without ':' is required")
    return uuid5(PROFILE_NAMESPACE, f"{kind}:{key}")


def customers() -> list[CustomerSpec]:
    """Return 96 fictional contacts; the importer must add no-email markers."""
    given_names = (
        "Aanya", "Vihaan", "Diya", "Arjun", "Ishita", "Kabir", "Meera", "Rohan",
        "Anika", "Dev", "Tara", "Aarav", "Nila", "Ishaan", "Sana", "Reyansh",
    )
    family_names = ("Rao", "Menon", "Shah", "Iyer", "Nair", "Kapoor")
    company_prefixes = (
        "Aster", "Pine", "Juniper", "Saffron", "Maple", "Cedar",
        "Olive", "Indigo", "Willow", "Lotus", "Clover", "Amber",
    )
    company_suffixes = (
        "Atelier", "Studio", "Collective", "House", "Workshop", "Mercantile",
        "Corner", "Gallery",
    )
    locations = (
        ("Kochi", "Kerala"), ("Bengaluru", "Karnataka"), ("Chennai", "Tamil Nadu"),
        ("Pune", "Maharashtra"), ("Jaipur", "Rajasthan"), ("Hyderabad", "Telangana"),
        ("Ahmedabad", "Gujarat"), ("Kolkata", "West Bengal"),
    )
    result: list[CustomerSpec] = []
    for index in range(CUSTOMER_COUNT):
        key = f"c{index + 1:03d}"
        city, state = locations[index % len(locations)]
        result.append({
            "id": record_id("customer", key),
            "display_name": (
                f"{given_names[index % len(given_names)]} "
                f"{family_names[index // len(given_names)]} (Demo)"
            ),
            "company_name": (
                f"{company_prefixes[index % len(company_prefixes)]} "
                f"{company_suffixes[index // len(company_prefixes)]} (Demo)"
            ),
            "email": f"{key}@{DEMO_CONTACT_DOMAIN}",
            "billing_address": {
                "line1": f"Demo Block {index + 1:03d}, Sample Avenue",
                "line2": "Fictional address for demonstration only",
                "city": city,
                "state": state,
                "postal_code": "000000",
                "country": "India",
            },
        })
    return result


def catalog() -> list[ProductSpec]:
    """Adapt the frozen 80 descriptions with independent synthetic INR prices."""
    manifest = json.loads(Path(__file__).with_name("online_retail_catalog.json").read_text())
    source_products = manifest["products"]
    if (
        len(source_products) != CATALOG_COUNT
        or len({row["stock_code"] for row in source_products}) != CATALOG_COUNT
        or any(not row["name"].strip() for row in source_products)
    ):
        raise ValueError("The frozen commerce catalog must contain 80 unique named products")
    price_points = tuple(Decimal(value) for value in (
        "249.00", "399.00", "599.00", "799.00", "999.00", "1299.00", "1599.00", "1999.00",
    ))
    result: list[ProductSpec] = []
    for index, source in enumerate(source_products):
        code = source["stock_code"]
        product_id = record_id("product", code)
        price = price_points[index % len(price_points)]
        result.append({
            "id": product_id,
            "stock_code": code,
            "original_description": source["original_description"],
            "name": source["name"],
            "product_type": "GOODS",
            "sales_price": price,
            "cost_price": money(price * Decimal("0.60")),
            "notes": (
                f"Demo catalog; source SKU {code}. Description adapted from Chen, D. (2015), "
                "Online Retail, UCI Machine Learning Repository, DOI:10.24432/C5BW33, "
                "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). "
                "Description normalized; INR price, cost and pack variants are fictional, "
                "not converted historical sterling prices. No endorsement is implied."
            ),
            "active": True,
            "variants": [
                {
                    "id": record_id("variant", f"{code}:gift"),
                    "product_id": product_id,
                    "attribute_name": "Pack",
                    "attribute_value": "Gift-ready (Demo)",
                    "price_delta": Decimal("49.00"),
                    "active": True,
                },
                {
                    "id": record_id("variant", f"{code}:pair"),
                    "product_id": product_id,
                    "attribute_name": "Pack",
                    "attribute_value": "Studio pair (Demo)",
                    "price_delta": price,
                    "active": True,
                },
            ],
        })
    return result


def _available_from(anchor: date) -> date:
    month_index = anchor.year * 12 + anchor.month - 1 - 6
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def plans(anchor: date) -> list[PlanSpec]:
    """Eight illustrative plans; availability starts six calendar months earlier."""
    definitions = (
        ("essential-monthly", "Essential monthly", "MONTHLY", "399.00"),
        ("studio-monthly", "Studio monthly", "MONTHLY", "899.00"),
        ("signature-monthly", "Signature monthly", "MONTHLY", "1499.00"),
        ("collective-monthly", "Collective monthly", "MONTHLY", "2499.00"),
        ("weekly-edit", "Weekly edit", "WEEKLY", "149.00"),
        ("daily-essentials", "Daily essentials", "DAILY", "49.00"),
        ("annual-reserve", "Annual reserve", "YEARLY", "5999.00"),
        ("annual-studio", "Annual studio", "YEARLY", "9999.00"),
    )
    return [
        {
            "id": record_id("plan", key),
            "name": f"{name} (Demo)",
            "base_fee": Decimal(fee),
            "currency": "INR",
            "cadence": cadence,
            "min_quantity": 1,
            "available_from": _available_from(anchor),
            "available_until": None,
            "allow_pause": True,
            "allow_early_close": True,
            "allow_renew": True,
            "auto_close": True,
        }
        for key, name, cadence, fee in definitions
    ]


def templates(anchor: date) -> list[TemplateSpec]:
    """Six suggested baskets; line quantities exclude the separate plan base fee."""
    product_specs = catalog()
    plan_specs = plans(anchor)
    names = (
        "Home essentials edit", "Studio welcome box", "Signature gifting selection",
        "Collective seasonal box", "Weekly discovery basket", "Daily tabletop edit",
    )
    result: list[TemplateSpec] = []
    for index, name in enumerate(names):
        key = f"basket-{index + 1}"
        lines: list[TemplateLineSpec] = []
        for line_index in range(3):
            product = product_specs[(index * 11 + line_index * 7) % len(product_specs)]
            variant = product["variants"][index % 2] if line_index == 0 else None
            lines.append({
                "id": record_id("template-line", f"{key}:{line_index + 1}"),
                "product_id": product["id"],
                "variant_id": variant["id"] if variant else None,
                "quantity": 1 + (index + line_index) % 3,
            })
        result.append({
            "id": record_id("template", key),
            "name": f"{name} (Demo)",
            "plan_id": plan_specs[index]["id"],
            "valid_days": 30,
            "active": True,
            "lines": lines,
        })
    return result

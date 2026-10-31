"""Explicit, idempotent fictional demo setup. Never resets existing data."""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, normalize_email, validate_password
from app.models import Plan, Product, ProductVariant, User


def demo_id(kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"https://cadentra.example.invalid/demo/{kind}")


def seed_demo(db: Session, email: str, password: str) -> dict[str, int]:
    """Caller owns the transaction. Never change a pre-existing user's role/password."""
    if not email or not password or password.startswith("REPLACE_"):
        raise ValueError("Provide local DEMO_ADMIN_EMAIL and compliant DEMO_ADMIN_PASSWORD")
    normalized = normalize_email(email)
    validate_password(password)
    created = {"users": 0, "products": 0, "variants": 0, "plans": 0}
    existing = db.scalar(select(User).where(User.normalized_email == normalized))
    if existing is not None and existing.role != "ADMIN":
        raise ValueError("Configured demo administrator email belongs to a non-admin account")
    if existing is None:
        db.add(User(id=demo_id("admin"), display_name="Demo administrator", normalized_email=normalized,
                    password_hash=hash_password(password), role="ADMIN", customer_id=None, active=True))
        created["users"] = 1
    if db.get(Product, demo_id("product")) is None:
        db.add(Product(id=demo_id("product"), name="Brightloop software seat", product_type="SERVICE",
                       sales_price=Decimal("1000.00"), cost_price=Decimal("600.00"),
                       notes="Fictional demo catalog; illustrative prices.", active=True))
        created["products"] = 1
    db.flush()  # Ensure the product exists before its variant FK is inserted.
    if db.get(ProductVariant, demo_id("variant")) is None:
        db.add(ProductVariant(id=demo_id("variant"), product_id=demo_id("product"),
                              attribute_name="Edition", attribute_value="Professional",
                              price_delta=Decimal("560.00"), active=True))
        created["variants"] = 1
    if db.get(Plan, demo_id("plan")) is None:
        db.add(Plan(id=demo_id("plan"), name="Brightloop monthly", base_fee=Decimal("0.00"),
                    currency="INR", cadence="MONTHLY", min_quantity=1,
                    available_from=date(2020, 1, 1), available_until=None,
                    allow_pause=True, allow_early_close=True, allow_renew=True, auto_close=True))
        created["plans"] = 1
    db.flush()
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", required=True,
                        help="Explicitly confirm this database is intended for fictional demo data")
    parser.parse_args()
    from app.core.config import get_settings
    from app.db.session import SessionFactory

    settings = get_settings()
    with SessionFactory.begin() as db:
        created = seed_demo(db, settings.demo_admin_email, settings.demo_admin_password)
    print("Demo seed committed; created " + ", ".join(f"{count} {kind}" for kind, count in created.items()))
    print("Existing records were preserved. No invoices, payments or external emails were fabricated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

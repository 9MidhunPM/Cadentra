"""Bootstrap/clean only T31-owned records in the assigned disposable database.

The browser creates all catalog, subscription and financial records through real
screens. This helper creates only admin/customer identities. Credentials and
observed UUIDs live in one private manifest directly under /tmp. Never run while
another verification process owns the database.
"""

import argparse
import json
import os
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AuditEvent,
    BillingPeriod,
    Customer,
    DiscountRedemption,
    DiscountRevisionProduct,
    DiscountRule,
    DiscountRuleRevision,
    EmailOutbox,
    Invoice,
    InvoiceLine,
    InvoiceLineTax,
    PasswordResetToken,
    Payment,
    Plan,
    PlanTax,
    Product,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    SessionRecord,
    Subscription,
    SubscriptionLine,
    SubscriptionPause,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
    User,
)

DATABASE = "cadentra_experience_test"
OWNED_KINDS = (
    "products",
    "variants",
    "plans",
    "tax_rules",
    "discount_rules",
    "templates",
    "subscriptions",
    "invoices",
    "payments",
)


def checked_engine():
    url = make_url(os.environ.get("DATABASE_URL", ""))
    if (
        os.environ.get("APP_ENV") != "test"
        or url.drivername != "postgresql+psycopg"
        or url.username != "cadentra"
        or url.host != "127.0.0.1"
        or url.port != 55431
        or url.database != DATABASE
    ):
        raise RuntimeError(
            "T31 requires APP_ENV=test and the assigned localhost:55431 experience_test database"
        )
    return create_engine(url, pool_pre_ping=True)


def checked_path(path: Path):
    if not path.is_absolute() or path.parent != Path("/tmp") or path.is_symlink():
        raise RuntimeError("Use a regular manifest directly under /tmp")


def seed(path: Path):
    checked_path(path)
    if path.exists():
        raise RuntimeError("Choose a new manifest filename; never overwrite an existing run")
    engine = checked_engine()
    manifest_created = False
    try:
        with Session(engine) as db, db.begin():
            # A global due-billing run and discount selection need an isolated dataset.
            for model in (
                User,
                Customer,
                Product,
                Plan,
                TaxRule,
                DiscountRule,
                QuotationTemplate,
                Subscription,
                Invoice,
            ):
                if db.scalar(select(func.count()).select_from(model)):
                    raise RuntimeError(
                        "T31 requires an empty disposable dataset; another run must finish cleanup first"
                    )
            run_id = str(uuid4())
            prefix = f"T31 {run_id}"
            customers = {}
            for key in ("A", "B"):
                row = Customer(
                    display_name=f"{prefix} Customer {key}", email=f"{uuid4()}@example.com"
                )
                db.add(row)
                db.flush()
                customers[key] = row
            actors = {}
            for key, role, customer_key in (
                ("admin", "ADMIN", None),
                ("customer_a", "CUSTOMER", "A"),
                ("customer_b", "CUSTOMER", "B"),
            ):
                password = secrets.token_urlsafe(24) + "Aa!"
                row = User(
                    display_name=f"{prefix} {key}",
                    normalized_email=f"{uuid4()}@example.com",
                    password_hash=hash_password(password),
                    role=role,
                    customer_id=customers[customer_key].id if customer_key else None,
                )
                db.add(row)
                db.flush()
                actors[key] = {
                    "id": str(row.id),
                    "email": row.normalized_email,
                    "password": password,
                    "role": role,
                }
            manifest = {
                "test_only": True,
                "kind": "cadentra-complete-journey",
                "database": DATABASE,
                "run_id": run_id,
                "prefix": prefix,
                "business_date": "2026-11-02",
                "service_end": "2026-12-02",
                "actors": actors,
                "customers": {
                    key: {"id": str(row.id), "name": row.display_name}
                    for key, row in customers.items()
                },
                "owned": {kind: [] for kind in OWNED_KINDS},
            }
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            manifest_created = True
            with os.fdopen(descriptor, "w") as output:
                json.dump(manifest, output, indent=2)
                output.flush()
                os.fsync(output.fileno())
    except Exception:
        if manifest_created:
            path.unlink()
        raise
    finally:
        engine.dispose()
    print(
        "T31 identities committed; private credentials/UUID manifest written. No business records seeded."
    )


def cleanup(path: Path):
    checked_path(path)
    if path.stat().st_mode & 0o077:
        raise RuntimeError("Manifest permissions must exclude group/other access")
    data = json.loads(path.read_text())
    if (
        data.get("test_only") is not True
        or data.get("kind") != "cadentra-complete-journey"
        or data.get("database") != DATABASE
    ):
        raise RuntimeError("Not a T31 disposable fixture manifest")
    UUID(data["run_id"])
    prefix = f"T31 {data['run_id']}"
    if data["prefix"] != prefix:
        raise RuntimeError("Fixture prefix does not match its run ID")
    customers = [UUID(item["id"]) for item in data["customers"].values()]
    users = [UUID(item["id"]) for item in data["actors"].values()]
    owned = {kind: [UUID(value) for value in data["owned"].get(kind, [])] for kind in OWNED_KINDS}
    engine = checked_engine()
    try:
        with Session(engine) as db, db.begin():
            for row in db.scalars(select(Customer).where(Customer.id.in_(customers))):
                if not row.display_name.startswith(prefix):
                    raise RuntimeError("Customer ownership verification failed")
            for row in db.scalars(select(User).where(User.id.in_(users))):
                if not row.display_name.startswith(prefix):
                    raise RuntimeError("User ownership verification failed")
            for model, kind in (
                (Product, "products"),
                (Plan, "plans"),
                (QuotationTemplate, "templates"),
            ):
                for row in db.scalars(select(model).where(model.id.in_(owned[kind]))):
                    if not row.name.startswith(prefix):
                        raise RuntimeError(f"Recorded {kind} ownership verification failed")
            tax_revisions = list(
                db.scalars(
                    select(TaxRuleRevision).where(
                        TaxRuleRevision.tax_rule_id.in_(owned["tax_rules"])
                    )
                )
            )
            discount_revisions = list(
                db.scalars(
                    select(DiscountRuleRevision).where(
                        DiscountRuleRevision.discount_rule_id.in_(owned["discount_rules"])
                    )
                )
            )
            if any(
                not row.name.startswith(prefix) for row in [*tax_revisions, *discount_revisions]
            ):
                raise RuntimeError("Rule revision ownership verification failed")
            tax_revision_ids = [row.id for row in tax_revisions]
            discount_revision_ids = [row.id for row in discount_revisions]
            # Recover generated financial descendants by our unique customer UUIDs,
            # even if the browser failed before observing their response IDs.
            subscriptions = list(
                db.scalars(select(Subscription.id).where(Subscription.customer_id.in_(customers)))
            )
            invoices = list(
                db.scalars(select(Invoice.id).where(Invoice.customer_id.in_(customers)))
            )
            lines = list(
                db.scalars(select(InvoiceLine.id).where(InvoiceLine.invoice_id.in_(invoices)))
            )
            entities = (
                customers
                + users
                + subscriptions
                + invoices
                + lines
                + tax_revision_ids
                + discount_revision_ids
            )
            for ids in owned.values():
                entities.extend(ids)
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.actor_user_id.in_(users) | AuditEvent.entity_id.in_(entities)
                )
            )
            db.execute(delete(EmailOutbox).where(EmailOutbox.aggregate_id.in_(entities)))
            db.execute(delete(SessionRecord).where(SessionRecord.user_id.in_(users)))
            db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id.in_(users)))
            db.execute(delete(Payment).where(Payment.invoice_id.in_(invoices)))
            db.execute(
                delete(DiscountRedemption).where(DiscountRedemption.invoice_id.in_(invoices))
            )
            db.execute(delete(InvoiceLineTax).where(InvoiceLineTax.invoice_line_id.in_(lines)))
            db.execute(delete(InvoiceLine).where(InvoiceLine.id.in_(lines)))
            db.execute(delete(Invoice).where(Invoice.id.in_(invoices)))
            db.execute(
                delete(BillingPeriod).where(BillingPeriod.subscription_id.in_(subscriptions))
            )
            db.execute(
                delete(SubscriptionPause).where(
                    SubscriptionPause.subscription_id.in_(subscriptions)
                )
            )
            db.execute(
                delete(SubscriptionLine).where(SubscriptionLine.subscription_id.in_(subscriptions))
            )
            db.execute(delete(Subscription).where(Subscription.id.in_(subscriptions)))
            db.execute(
                delete(QuotationTemplateLine).where(
                    QuotationTemplateLine.template_id.in_(owned["templates"])
                )
            )
            db.execute(
                delete(QuotationTemplate).where(QuotationTemplate.id.in_(owned["templates"]))
            )
            db.execute(delete(PlanTax).where(PlanTax.plan_id.in_(owned["plans"])))
            db.execute(delete(Plan).where(Plan.id.in_(owned["plans"])))
            db.execute(
                delete(TaxRevisionProduct).where(
                    TaxRevisionProduct.tax_rule_revision_id.in_(tax_revision_ids)
                )
            )
            db.execute(
                delete(DiscountRevisionProduct).where(
                    DiscountRevisionProduct.discount_rule_revision_id.in_(discount_revision_ids)
                )
            )
            db.execute(delete(TaxRuleRevision).where(TaxRuleRevision.id.in_(tax_revision_ids)))
            db.execute(
                delete(DiscountRuleRevision).where(
                    DiscountRuleRevision.id.in_(discount_revision_ids)
                )
            )
            db.execute(delete(TaxRule).where(TaxRule.id.in_(owned["tax_rules"])))
            db.execute(delete(DiscountRule).where(DiscountRule.id.in_(owned["discount_rules"])))
            db.execute(
                delete(ProductVariant).where(ProductVariant.product_id.in_(owned["products"]))
            )
            db.execute(delete(Product).where(Product.id.in_(owned["products"])))
            db.execute(delete(User).where(User.id.in_(users)))
            db.execute(delete(Customer).where(Customer.id.in_(customers)))
    finally:
        engine.dispose()
    path.unlink()
    print("Removed only recorded T31 UUIDs, their owned descendants, and the private manifest.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("seed", "cleanup"))
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    (seed if args.operation == "seed" else cleanup)(args.manifest)

"""Explicit T30 dataset, restricted to the assigned disposable PostgreSQL database.

Each run uses a UUID namespace in cadentra_performance_test, migrated by Alembic.
Cleanup proves namespace ownership before dropping only that generated schema.
"""

import argparse
import json
import os
import platform
import secrets
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fixture_database import (
    base_url,
    create_namespace,
    drop_namespace,
    manifest_path,
    namespace,
    read_manifest,
    scoped_url,
    verify_namespace,
)
from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.models import (
    BillingPeriod,
    Customer,
    DiscountRevisionProduct,
    DiscountRule,
    DiscountRuleRevision,
    Invoice,
    InvoiceLine,
    Payment,
    Plan,
    Product,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionLine,
    TaxRevisionProduct,
    TaxRule,
    TaxRuleRevision,
    User,
)
from app.modules.catalog.service import get_plan_snapshot, get_product_snapshot

SUBSCRIPTIONS = 5000
INVOICES = 20000
BATCH = 500


def chunks(values):
    for offset in range(0, len(values), BATCH):
        yield values[offset : offset + BATCH]


def seed(path):
    manifest_path(path)
    if path.exists():
        raise RuntimeError("Manifest already exists; cleanup its dataset first")
    run = str(uuid4())
    metadata = {
        "test_only": True,
        "kind": "T30",
        "database": base_url().database,
        "run": run,
        "schema": namespace(run),
        "state": "preparing",
    }
    # Preserve a private recovery manifest even if migration/seed fails.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(metadata, output)
    create_namespace(metadata)
    engine = create_engine(scoped_url(metadata))
    short_run = UUID(run).hex[:12]
    started = time.monotonic()
    customer_ids = [uuid4(), uuid4()]
    plan_id = uuid4()
    staff_id, customer_user_id, admin_id = uuid4(), uuid4(), uuid4()
    product_id, variant_id, template_id, template_line_id = [uuid4() for _ in range(4)]
    tax_id, tax_revision_id, discount_id, discount_revision_id = [uuid4() for _ in range(4)]
    actors = {}
    rows = {
        key: []
        for key in [
            "subscriptions",
            "subscription_lines",
            "periods",
            "invoices",
            "lines",
            "payments",
        ]
    }
    first_subscription = first_invoice = paid_invoice = partial_invoice = None
    with engine.begin() as connection:
        if connection.scalar(select(func.count()).select_from(Subscription)) or connection.scalar(
            select(func.count()).select_from(Invoice)
        ):
            raise RuntimeError("T30 requires an empty disposable reporting dataset")
        connection.execute(
            insert(Customer),
            [
                {
                    "id": ident,
                    "display_name": f"T30 Fictional Customer {index + 1}",
                    "email": f"t30-{run}-{index}@example.com",
                    "billing_address": {"city": "Fictional City", "country": "IN"},
                }
                for index, ident in enumerate(customer_ids)
            ],
        )
        connection.execute(
            insert(Plan),
            {
                "id": plan_id,
                "name": "T30 fictional monthly service",
                "base_fee": Decimal("0.00"),
                "cadence": "MONTHLY",
                "available_from": date(2026, 1, 1),
                "min_quantity": 1,
            },
        )
        connection.execute(
            insert(Product),
            {
                "id": product_id,
                "name": "T30 fictional service",
                "product_type": "SERVICE",
                "sales_price": Decimal("100.00"),
                "cost_price": Decimal("20.00"),
            },
        )
        connection.execute(
            insert(ProductVariant),
            {
                "id": variant_id,
                "product_id": product_id,
                "attribute_name": "Tier",
                "attribute_value": "Standard",
                "price_delta": Decimal("0.00"),
            },
        )
        connection.execute(
            insert(QuotationTemplate),
            {
                "id": template_id,
                "name": "T30 fictional quotation",
                "plan_id": plan_id,
                "valid_days": 30,
            },
        )
        connection.execute(
            insert(QuotationTemplateLine),
            {
                "id": template_line_id,
                "template_id": template_id,
                "product_id": product_id,
                "variant_id": variant_id,
                "quantity": 1,
            },
        )
        # Rules exist today, but do not retroactively affect July–October invoices.
        effective = date(2026, 11, 2)
        connection.execute(insert(TaxRule), {"id": tax_id})
        connection.execute(
            insert(TaxRuleRevision),
            {
                "id": tax_revision_id,
                "tax_rule_id": tax_id,
                "effective_from": effective,
                "valid_from": effective,
                "name": "T30 illustrative tax",
                "rate_percent": Decimal("18.0000"),
            },
        )
        connection.execute(
            insert(TaxRevisionProduct),
            {
                "tax_rule_revision_id": tax_revision_id,
                "product_id": product_id,
            },
        )
        connection.execute(insert(DiscountRule), {"id": discount_id})
        connection.execute(
            insert(DiscountRuleRevision),
            {
                "id": discount_revision_id,
                "discount_rule_id": discount_id,
                "effective_from": effective,
                "starts_on": effective,
                "name": "T30 illustrative discount",
                "kind": "PERCENT",
                "value": Decimal("10.0000"),
                "scope": "PRODUCTS",
                "min_purchase": Decimal("0.00"),
                "min_quantity": 1,
            },
        )
        connection.execute(
            insert(DiscountRevisionProduct),
            {
                "discount_rule_revision_id": discount_revision_id,
                "product_id": product_id,
            },
        )
        with Session(bind=connection) as db:
            plan_snapshot = get_plan_snapshot(db, plan_id, date(2026, 7, 1))
            product_snapshot = get_product_snapshot(db, product_id, variant_id, date(2026, 7, 1))
        for key, ident, role in [
            ("admin", admin_id, "ADMIN"),
            ("staff", staff_id, "STAFF"),
            ("customer_a", customer_user_id, "CUSTOMER"),
        ]:
            password = secrets.token_urlsafe(24) + "Aa!"
            email = f"t30-{run}-{key}@example.com"
            connection.execute(
                insert(User),
                {
                    "id": ident,
                    "display_name": f"T30 {key}",
                    "normalized_email": email,
                    "password_hash": hash_password(password),
                    "role": role,
                    "customer_id": customer_ids[0] if role == "CUSTOMER" else None,
                },
            )
            actors[key] = {"id": str(ident), "email": email, "password": password}
        # Four real, nonoverlapping monthly periods per subscription. The fixed
        # test app date is November 2; all subscriptions remain active until Dec 1.
        boundaries = [date(2026, month, 1) for month in range(7, 12)]
        subs, sub_lines, periods, invoices, lines, payments = [], [], [], [], [], []
        for index in range(SUBSCRIPTIONS):
            subscription_id = uuid4()
            customer_id = customer_ids[index % 2]
            subscription_number = f"T30-S-{short_run}-{index:05d}"
            rows["subscriptions"].append(str(subscription_id))
            subs.append(
                {
                    "id": subscription_id,
                    "number": subscription_number,
                    "customer_id": customer_id,
                    "plan_id": plan_id,
                    "state": "ACTIVE",
                    "start_date": boundaries[0],
                    "end_date": date(2026, 12, 1),
                    "next_cycle_index": 4,
                    "payment_terms_days": 14,
                    "plan_snapshot": plan_snapshot,
                    "created_at": datetime(2026, 7, 1, tzinfo=UTC) + timedelta(seconds=index),
                }
            )
            sub_line_id = uuid4()
            rows["subscription_lines"].append(str(sub_line_id))
            sub_lines.append(
                {
                    "id": sub_line_id,
                    "subscription_id": subscription_id,
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "description": product_snapshot["description"],
                    "quantity": 1,
                    "unit_price": Decimal("100.00"),
                    "price_snapshot": product_snapshot["price_snapshot"],
                    "selected_tax_ids": product_snapshot["selected_tax_ids"],
                }
            )
            if index == 0:
                first_subscription = {"id": str(subscription_id), "number": subscription_number}
            for cycle in range(4):
                period_id, invoice_id, line_id, payment_id, base_line_id = [
                    uuid4() for _ in range(5)
                ]
                paid = (index // 2 + cycle) % 2 == 0
                invoice_number = f"T30-I-{short_run}-{index:05d}-{cycle}"
                for key, ident in [
                    ("periods", period_id),
                    ("invoices", invoice_id),
                    ("lines", line_id),
                    ("payments", payment_id),
                ]:
                    rows[key].append(str(ident))
                rows["lines"].append(str(base_line_id))
                periods.append(
                    {
                        "id": period_id,
                        "subscription_id": subscription_id,
                        "cycle_index": cycle,
                        "period_start": boundaries[cycle],
                        "period_end": boundaries[cycle + 1],
                        "disposition": "INVOICED",
                    }
                )
                invoices.append(
                    {
                        "id": invoice_id,
                        "number": invoice_number,
                        "subscription_id": subscription_id,
                        "billing_period_id": period_id,
                        "customer_id": customer_id,
                        "status": "PAID" if paid else "CONFIRMED",
                        "currency": "INR",
                        "invoice_date": boundaries[cycle],
                        "due_date": boundaries[cycle] + timedelta(days=14),
                        "customer_snapshot": {
                            "display_name": f"T30 Fictional Customer {index % 2 + 1}"
                        },
                        "seller_snapshot": {"name": "Brightloop Software"},
                        "subtotal": Decimal("100.00"),
                        "discount_total": Decimal("0.00"),
                        "tax_total": Decimal("0.00"),
                        "total": Decimal("100.00"),
                        "confirmed_at": datetime.combine(
                            boundaries[cycle], datetime.min.time(), UTC
                        ),
                        "calculation_snapshot": {
                            "schema_version": 1,
                            "rounding": "ROUND_HALF_UP",
                            "tax_policy": "after_discount_noncompounding",
                            "subscription_revision": 1,
                            "discount_kind": None,
                            "discount_value": "0.00",
                            "discount_reason": "No eligible positive discount",
                            "line_keys": ["BASE", str(sub_line_id)],
                            "lines": [
                                {
                                    "stable_line_key": key,
                                    "quantity": 1,
                                    "unit_price": amount,
                                    "gross": amount,
                                    "discount": "0.00",
                                    "taxable_amount": amount,
                                    "tax_total": "0.00",
                                    "total": amount,
                                    "price_components": components,
                                    "taxes": [],
                                }
                                for key, amount, components in [
                                    ("BASE", "0.00", {"base_fee": "0.00"}),
                                    (
                                        str(sub_line_id),
                                        "100.00",
                                        product_snapshot["price_snapshot"],
                                    ),
                                ]
                            ],
                        },
                    }
                )
                for ident, key, amount, product, variant, snapshot, description in [
                    (base_line_id, "BASE", "0.00", None, None, plan_snapshot, "Plan base fee"),
                    (
                        line_id,
                        str(sub_line_id),
                        "100.00",
                        product_id,
                        variant_id,
                        product_snapshot["price_snapshot"],
                        product_snapshot["description"],
                    ),
                ]:
                    lines.append(
                        {
                            "id": ident,
                            "invoice_id": invoice_id,
                            "stable_line_key": key,
                            "description": description,
                            "quantity": 1,
                            "product_id": product,
                            "variant_id": variant,
                            "unit_price": Decimal(amount),
                            "gross": Decimal(amount),
                            "discount": Decimal("0.00"),
                            "taxable_amount": Decimal(amount),
                            "tax_total": Decimal("0.00"),
                            "total": Decimal(amount),
                            "source_snapshot": snapshot,
                        }
                    )
                payments.append(
                    {
                        "id": payment_id,
                        "invoice_id": invoice_id,
                        "method": "MANUAL",
                        "amount": Decimal("100.00" if paid else "50.00"),
                        "paid_on": boundaries[cycle] + timedelta(days=1),
                        "created_by": staff_id,
                        "request_key": f"t30-{run}-{index}-{cycle}",
                        "request_payload_hash": "0" * 64,
                    }
                )
                if index == 0 and cycle == 0:
                    first_invoice = {"id": str(invoice_id), "number": invoice_number}
                if index == 0:
                    ref = {
                        "id": str(invoice_id),
                        "number": invoice_number,
                        "total": "100.00",
                        "paid_amount": "100.00" if paid else "50.00",
                        "balance_due": "0.00" if paid else "50.00",
                        "status": "PAID" if paid else "CONFIRMED",
                    }
                    if paid and paid_invoice is None:
                        paid_invoice = ref
                    if not paid and partial_invoice is None:
                        partial_invoice = ref
        for model, values in [
            (Subscription, subs),
            (SubscriptionLine, sub_lines),
            (BillingPeriod, periods),
            (Invoice, invoices),
            (InvoiceLine, lines),
            (Payment, payments),
        ]:
            for batch in chunks(values):
                connection.execute(insert(model), batch)
        counts = {}
        for model, expected in [
            (Subscription, SUBSCRIPTIONS),
            (SubscriptionLine, SUBSCRIPTIONS),
            (Customer, 2),
            (Product, 1),
            (ProductVariant, 1),
            (Plan, 1),
            (QuotationTemplate, 1),
            (TaxRule, 1),
            (DiscountRule, 1),
            (TaxRuleRevision, 1),
            (DiscountRuleRevision, 1),
            (TaxRevisionProduct, 1),
            (DiscountRevisionProduct, 1),
            (QuotationTemplateLine, 1),
            (User, 3),
            (BillingPeriod, INVOICES),
            (Invoice, INVOICES),
            (InvoiceLine, INVOICES * 2),
            (Payment, INVOICES),
        ]:
            count = connection.scalar(select(func.count()).select_from(model))
            if count != expected:
                raise RuntimeError(f"{model.__tablename__}: expected {expected}, found {count}")
            counts[model.__tablename__] = count
        # Reconcile persisted money, not just row counts, before committing.
        financial = {
            "invoiced": str(connection.scalar(select(func.sum(Invoice.total)))),
            "cash": str(connection.scalar(select(func.sum(Payment.amount)))),
            "paid_invoices": connection.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.status == "PAID")
            ),
            "partial_invoices": connection.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.status == "CONFIRMED")
            ),
        }
        if financial != {
            "invoiced": "2000000.00",
            "cash": "1500000.00",
            "paid_invoices": 10000,
            "partial_invoices": 10000,
        }:
            raise RuntimeError("Persisted T30 financial reconciliation failed")
        financial["outstanding"] = str(Decimal(financial["invoiced"]) - Decimal(financial["cash"]))
        customer_filter = Invoice.customer_id == customer_ids[0]
        confirmed = Invoice.status == "CONFIRMED"
        october = (Invoice.invoice_date >= date(2026, 10, 1)) & (
            Invoice.invoice_date < date(2026, 11, 1)
        )

        def invoice_count(*conditions):
            return connection.scalar(select(func.count()).select_from(Invoice).where(*conditions))

        persisted_filters = {
            "customer_invoices": invoice_count(customer_filter),
            "customer_confirmed": invoice_count(customer_filter, confirmed),
            "overdue": invoice_count(confirmed, Invoice.due_date < date(2026, 11, 2)),
            "customer_overdue": invoice_count(
                customer_filter, confirmed, Invoice.due_date < date(2026, 11, 2)
            ),
            "October_all": invoice_count(october),
            "customer_October_confirmed": invoice_count(customer_filter, confirmed, october),
            "customer_invoiced": str(
                connection.scalar(select(func.sum(Invoice.total)).where(customer_filter))
            ),
            "customer_cash": str(
                connection.scalar(
                    select(func.sum(Payment.amount))
                    .join(Invoice, Payment.invoice_id == Invoice.id)
                    .where(customer_filter)
                )
            ),
            "customer_active": connection.scalar(
                select(func.count())
                .select_from(Subscription)
                .where(Subscription.customer_id == customer_ids[0], Subscription.state == "ACTIVE")
            ),
        }
        if persisted_filters != {
            "customer_invoices": 10000,
            "customer_confirmed": 5000,
            "overdue": 10000,
            "customer_overdue": 5000,
            "October_all": 5000,
            "customer_October_confirmed": 1250,
            "customer_invoiced": "1000000.00",
            "customer_cash": "750000.00",
            "customer_active": 2500,
        }:
            raise RuntimeError("Persisted T30 route filter reconciliation failed")
        data = {
            **metadata,
            "state": "ready",
            "actors": actors,
            "customers": [str(value) for value in customer_ids],
            "plan_id": str(plan_id),
            "record_ids": rows,
            "first_subscription": first_subscription,
            "first_invoice": first_invoice,
            "paid_invoice": paid_invoice,
            "partial_invoice": partial_invoice,
            "customer_names": ["T30 Fictional Customer 1", "T30 Fictional Customer 2"],
            "reset_form_token": "fixture-form-only-invalid",
            "refs": {
                "product": {"id": str(product_id), "name": "T30 fictional service"},
                "variant": {
                    "id": str(variant_id),
                    "attribute_name": "Tier",
                    "attribute_value": "Standard",
                },
                "plan": {
                    "id": str(plan_id),
                    "name": "T30 fictional monthly service",
                    "base_fee": "0.00",
                },
                "template": {
                    "id": str(template_id),
                    "name": "T30 fictional quotation",
                    "valid_days": 30,
                },
                "tax": {
                    "id": str(tax_id),
                    "name": "T30 illustrative tax",
                    "rate_percent": "18.0000",
                },
                "discount": {
                    "id": str(discount_id),
                    "name": "T30 illustrative discount",
                    "kind": "PERCENT",
                    "value": "10.0000",
                },
            },
            "counts": counts,
            "financial_reconciliation": financial,
            "filter_reconciliation": persisted_filters,
            "expected": {
                "active": 5000,
                "customer_active": 2500,
                "invoiced": "2000000.00",
                "cash": "1500000.00",
                "outstanding": "500000.00",
                "customer_invoiced": "1000000.00",
                "customer_cash": "750000.00",
                "customer_outstanding": "250000.00",
                "customer_invoices": 10000,
                "overdue": 10000,
                "customer_overdue": 5000,
                "customer_confirmed": 5000,
                "October_all": 5000,
                "customer_October_confirmed": 1250,
                "invoice_lines_count": 2,
            },
            "seed_environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "postgresql": connection.scalar(text("SELECT version()")),
                "seed_seconds": time.monotonic() - started,
            },
        }
        # Every seeded UUID and composite membership is recorded for read-only verification.
        data["table_ids"] = {
            table.name: sorted(str(value) for value in connection.scalars(select(table.c.id)))
            for table in Base.metadata.sorted_tables
            if "id" in table.c
        }
        data["memberships"] = {
            "tax_revision_products": [
                {"tax_rule_revision_id": str(tax_revision_id), "product_id": str(product_id)}
            ],
            "discount_revision_products": [
                {
                    "discount_rule_revision_id": str(discount_revision_id),
                    "product_id": str(product_id),
                }
            ],
        }
    # The data transaction is committed before the ready manifest becomes visible.
    with path.open("w") as output:
        json.dump(data, output)

    engine.dispose()
    print(f"Committed T30 fixture: {counts}; private manifest saved.")


def verify(path):
    data = read_manifest(path)
    engine = create_engine(base_url(data))
    try:
        with engine.connect() as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            verify_namespace(db, data)
    finally:
        engine.dispose()
    if data.get("state") == "ready":
        scoped = create_engine(scoped_url(data))
        try:
            with scoped.connect() as db:
                db.execute(text("SET TRANSACTION READ ONLY"))
                actor_ids = {actor["id"] for actor in data["actors"].values()}
                for table in Base.metadata.sorted_tables:
                    if "id" not in table.c:
                        continue
                    if table.name == "sessions":
                        if any(
                            str(value) not in actor_ids
                            for value in db.scalars(select(table.c.user_id))
                        ):
                            raise RuntimeError("Unrecorded session owner in fixture namespace")
                    elif table.name == "audit_events":
                        if any(
                            str(value) not in actor_ids
                            for value in db.scalars(select(table.c.actor_user_id))
                        ):
                            raise RuntimeError("Unrecorded audit actor in fixture namespace")
                    elif (
                        sorted(str(value) for value in db.scalars(select(table.c.id)))
                        != data["table_ids"][table.name]
                    ):
                        raise RuntimeError(f"Fixture UUID inventory changed: {table.name}")
                for name, records in data["memberships"].items():
                    table = Base.metadata.tables[name]
                    actual = [
                        {key: str(value) for key, value in row.items()}
                        for row in db.execute(select(table)).mappings()
                    ]
                    if actual != records:
                        raise RuntimeError(f"Fixture membership inventory changed: {name}")
        finally:
            scoped.dispose()
    print("Verified exact T30 database, UUID namespace ownership and recorded row inventory.")
    return data


def cleanup(path):
    data = verify(path)
    drop_namespace(data)
    path.unlink()
    print("Removed only the verified T30 UUID namespace and private manifest.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["seed", "verify", "cleanup"])
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    {"seed": seed, "verify": verify, "cleanup": cleanup}[args.operation](args.manifest)

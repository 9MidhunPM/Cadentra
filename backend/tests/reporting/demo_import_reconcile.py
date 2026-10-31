"""Read-only disposable-import SQL versus reporting HTTP-route reconciliation.

Run with the coordinator's current backend on PYTHONPATH. Authentication is an
explicit in-process ADMIN override; this does not prove production auth/networking.
No importer, worker, email operation, seed, commit or production connection runs.
"""

import argparse
import calendar
import json
import os
import stat
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.credentials_file
    info = path.stat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.getuid()
    ):
        raise ValueError("A privately owned mode0600 credential reference is required")
    config = json.loads(path.read_text())
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    url = make_url(config["url"])
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.port != 55431
        or not (url.database or "").endswith("_test")
        or url.database != config["database"]
        or url.database in {"cadentra_experience_test", "cadentra_performance_test"}
        or url.query
    ):
        raise ValueError("Only the explicitly supplied new local import test database is allowed")
    os.environ.update(
        APP_ENV="test",
        DATABASE_URL=config["url"],
        TEST_DATABASE_URL=config["url"],
        SMTP_HOST="localhost",
    )
    from fastapi.testclient import TestClient

    from app.core.auth import Actor, Role, require_actor
    from app.core.clock import get_clock
    from app.db.session import get_session
    from app.main import create_app

    engine = create_engine(
        url,
        isolation_level="REPEATABLE READ",
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    checks = []
    today = get_clock().today()
    first_year, first_month = divmod(today.year * 12 + today.month - 1 - 6, 12)
    start, end = date(first_year, first_month + 1, 1), today + timedelta(days=1)

    def money(value):
        return format(value or Decimal("0.00"), ".2f")

    with Session(engine) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        assert db.scalar(text("SHOW transaction_read_only")) == "on"
        admin = db.execute(
            text("SELECT id FROM users WHERE role='ADMIN' AND active ORDER BY id LIMIT 1")
        ).scalar_one()
        actor = Actor(admin, Role.ADMIN, None, "Read-only reconciliation")
        cohort = list(
            db.scalars(
                text(
                    "SELECT entity_id FROM audit_events WHERE entity_type='subscription' "
                    "AND action='DEMO_SEED_SCENARIO' AND redacted_details->>'dataset'='uci-retail-fictional-v1'"
                )
            )
        )
        assert len(cohort) == len(set(cohort)) == 192
        common = {"ids": cohort, "today": today, "start": start, "end": end}
        cohort_sql = "subscription_id = ANY(:ids)"
        states = dict(
            db.execute(
                text("SELECT state,count(*) FROM subscriptions WHERE id=ANY(:ids) GROUP BY state"),
                common,
            ).all()
        )
        assert states == {"ACTIVE": 96, "DRAFT": 24, "QUOTATION": 24, "CONFIRMED": 24, "CLOSED": 24}
        invoices = db.execute(
            text(f"SELECT status,count(*) FROM invoices WHERE {cohort_sql} GROUP BY status"), common
        ).all()
        totals = db.execute(
            text(f"""
            WITH i AS (SELECT * FROM invoices WHERE {cohort_sql}),
            p AS (SELECT p.invoice_id,sum(p.amount) AS paid FROM payments p JOIN i ON i.id=p.invoice_id GROUP BY p.invoice_id)
            SELECT (SELECT count(*) FROM i),
                   (SELECT count(*) FROM payments p JOIN i ON i.id=p.invoice_id),
                   (SELECT count(*) FROM billing_periods WHERE subscription_id=ANY(:ids)),
                   (SELECT sum(total) FROM i WHERE status IN ('CONFIRMED','PAID')),
                   (SELECT sum(p.amount) FROM payments p JOIN i ON i.id=p.invoice_id),
                   (SELECT sum(i.total-coalesce(p.paid,0)) FROM i LEFT JOIN p ON p.invoice_id=i.id WHERE i.status='CONFIRMED'),
                   (SELECT count(*) FROM email_outbox e JOIN i ON i.id=e.aggregate_id)
        """),
            common,
        ).one()
        cohort_result = {
            "subscriptions": len(cohort),
            "states": states,
            "invoice_states": dict(invoices),
            "invoices": totals[0],
            "payments": totals[1],
            "billing_periods": totals[2],
            "invoiced_gross": money(totals[3]),
            "cash_received": money(totals[4]),
            "outstanding": money(totals[5]),
            "outbound_emails": totals[6],
        }
        assert (totals[0], totals[1], totals[2], totals[6]) == (624, 843, 648, 0)
        checks.append("cohort IDs/states/financial counts/no-email independently reconciled")

        def expected(customer=None):
            params = common | {"customer": customer}
            customer_i = " AND i.customer_id=:customer" if customer else ""
            customer_s = " AND s.customer_id=:customer" if customer else ""
            active = db.scalar(
                text(
                    """SELECT count(*) FROM subscriptions s WHERE s.state='ACTIVE'
                AND s.start_date<=:today AND s.end_date>:today
                AND (s.close_effective_on IS NULL OR s.close_effective_on>:today)
                AND NOT EXISTS (SELECT 1 FROM subscription_pauses p WHERE p.subscription_id=s.id
                    AND p.starts_on<=:today AND (p.ends_on IS NULL OR p.ends_on>:today))"""
                    + customer_s
                ),
                params,
            )
            gross = db.scalar(
                text(
                    "SELECT sum(i.total) FROM invoices i WHERE i.status IN ('CONFIRMED','PAID') "
                    "AND i.invoice_date>=:start AND i.invoice_date<:end" + customer_i
                ),
                params,
            )
            cash = db.scalar(
                text(
                    "SELECT sum(p.amount) FROM payments p JOIN invoices i ON i.id=p.invoice_id "
                    "WHERE p.paid_on>=:start AND p.paid_on<:end" + customer_i
                ),
                params,
            )
            debt = db.execute(
                text(
                    """WITH p AS (SELECT invoice_id,sum(amount) paid FROM payments GROUP BY invoice_id)
                SELECT coalesce(sum(i.total-coalesce(p.paid,0)),0),
                       coalesce(sum(i.total-coalesce(p.paid,0)) FILTER(WHERE i.due_date<:today),0),
                       count(*) FILTER(WHERE i.due_date<:today)
                FROM invoices i LEFT JOIN p ON p.invoice_id=i.id
                WHERE i.status='CONFIRMED' AND i.total>coalesce(p.paid,0)"""
                    + customer_i
                ),
                params,
            ).one()
            return {
                "as_of": str(today),
                "range_from": str(start),
                "range_to": str(end),
                "currency": "INR",
                "active_subscriptions": active,
                "invoiced_gross_in_range": money(gross),
                "cash_received_in_range": money(cash),
                "outstanding_now": money(debt[0]),
                "overdue_now": money(debt[1]),
                "overdue_invoice_count": debt[2],
            }

        app = create_app()
        app.dependency_overrides[require_actor] = lambda: actor
        app.dependency_overrides[get_session] = lambda: db
        customer = db.scalar(
            text(
                "SELECT customer_id FROM subscriptions WHERE id=ANY(:ids) ORDER BY customer_id LIMIT 1"
            ),
            common,
        )
        summaries = {}
        with TestClient(app) as client:
            for label, selected in (("global", None), ("sample_customer", customer)):
                wanted = expected(selected)
                params = {"from": str(start), "to": str(end)} | (
                    {"customer_id": str(selected)} if selected else {}
                )
                response = client.get("/api/v1/reports/summary", params=params)
                assert response.status_code == 200
                actual = response.json()["data"]
                assert all(actual[key] == value for key, value in wanted.items())
                summaries[label] = wanted
                checks.append(label + " summary exact SQL/API equality")
                customer_sql = " AND i.customer_id=:customer" if selected else ""
                values = common | {"customer": selected}
                gross_days = dict(
                    db.execute(
                        text(
                            "SELECT i.invoice_date,sum(i.total) FROM invoices i "
                            "WHERE i.status IN ('CONFIRMED','PAID') AND i.invoice_date>=:start AND i.invoice_date<:end"
                            + customer_sql
                            + " GROUP BY i.invoice_date"
                        ),
                        values,
                    ).all()
                )
                cash_days = dict(
                    db.execute(
                        text(
                            "SELECT p.paid_on,sum(p.amount) FROM payments p JOIN invoices i ON i.id=p.invoice_id "
                            "WHERE p.paid_on>=:start AND p.paid_on<:end"
                            + customer_sql
                            + " GROUP BY p.paid_on"
                        ),
                        values,
                    ).all()
                )
                for cadence in ("DAILY", "MONTHLY"):
                    buckets, cursor = [], start
                    while cursor < end:
                        days = (
                            1
                            if cadence == "DAILY"
                            else calendar.monthrange(cursor.year, cursor.month)[1] - cursor.day + 1
                        )
                        until = min(cursor + timedelta(days=days), end)
                        day, gross, cash = cursor, Decimal(0), Decimal(0)
                        while day < until:
                            gross += gross_days.get(day, Decimal(0))
                            cash += cash_days.get(day, Decimal(0))
                            day += timedelta(days=1)
                        buckets.append(
                            {
                                "period_start": str(cursor),
                                "period_end": str(until),
                                "invoiced_gross": money(gross),
                                "cash_received": money(cash),
                            }
                        )
                        cursor = until
                    response = client.get(
                        "/api/v1/reports/revenue-series", params=params | {"cadence": cadence}
                    )
                    assert (
                        response.status_code == 200
                        and response.json()["data"]["buckets"] == buckets
                    )
                    checks.append(label + " " + cadence + " series exact SQL/API equality")
                for kind in ("OVERDUE", "BILLING_DUE", "EMAIL_FAILED"):
                    response = client.get(
                        "/api/v1/reports/cycleguard",
                        params={"kind": kind}
                        | ({"customer_id": str(selected)} if selected else {}),
                    )
                    assert response.status_code == 200
                    result = response.json()
                    assert (
                        result["as_of"] == str(today)
                        and result["page"] == 1
                        and result["page_size"] == 25
                    )
                    assert result["total"] == (
                        wanted["overdue_invoice_count"] if kind == "OVERDUE" else 0
                    )
                    assert len({row["id"] for row in result["items"]}) == len(result["items"])
                    checks.append(label + " CycleGuard " + kind + " count/source projection")
        db.rollback()
    engine.dispose()
    evidence = {
        "status": "passed",
        "scope": "new disposable import test database only",
        "read_only": True,
        "authentication": "in-process ADMIN dependency override; not production auth/network proof",
        "cohort": cohort_result,
        "summaries": summaries,
        "checks": checks,
        "production_writes": False,
        "provider_operations": False,
    }
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(evidence, output, indent=2)
    print(json.dumps(evidence))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None

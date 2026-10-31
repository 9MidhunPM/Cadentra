# Billing verification

Status: financial API, recurring issuer, corrected billing UI and URL drilldowns integrated through main 00ffa99. Joint lifecycle/worker checks and the full T31 functional browser journey pass. Final billing-page performance remains an integration gate.

## Commands

Use the reviewed backend lock and Python 3.12:

```sh
uv sync --project backend --frozen --python 3.12
python3 scripts/check_pack.py
python3 backend/tests/billing/check_prepared_cases.py
backend/.venv/bin/pytest backend/tests/billing -q
```

Set DATABASE_URL and TEST_DATABASE_URL to this workspace's isolated PostgreSQL databases. TEST_DATABASE_URL must end in _test. Never point financial tests at a production/shared application database.

The preparation checker compares six canonical and nine additional fixtures with the planning reference only. test_pricing.py runs those 15 vectors against the actual calculator. Passing reference checks alone is not application evidence.

## Actual coverage

- test_pricing.py: Decimal cents, deterministic largest-remainder allocation, separate additive taxes, immutable inputs/results and stored-precision/bounds validation.
- test_rules.py: real rule/API permissions, immutable effective-dated revisions, scoped minimums/date/cap eligibility and locked best-rule selection.
- test_invoices.py: persisted queries, partial/full/zero settlement, matching/conflicting keys, cancellation, safe customer projection, escaped print, queued email and strict HTTP guards.
- test_invoice_races.py: eight cases force both invoice-lock acquisition orders for payment capacity, matching payment replay, cancellation and matching sends. A third physical connection proves the loser is waiting on the actual PostgreSQL lock. Fixture cleanup removes only its generated UUID graph in an explicitly disposable test database.
- test_issuance.py: one period/invoice under contention, one remaining global discount use, issued detail/print after a real retained-rate edit, cancelled discounted period replay, actual rollback/23505 recovery, shortened full-cycle pricing, paused catch-up and failed-prefix progress across a fresh interpreter.
- test_run_due_api.py: actual authentication/role/CSRF guards, strict empty input and server-owned clock/batch size.

Committed issuance fixtures create a generated UUID PostgreSQL schema, migrate it with the reviewed Alembic head, run all connections there, then drop only that schema after workers finish. No public truncation, database drops or disabled history triggers are used. Existing public test data is not silently erased.

A clean generated-schema combined backend run passed 329 tests and 121 subtests after reviewed main beedbbd, including the actual joint worker and subscription-action races. Exact commands, source commit and verification are recorded in [Noel's handoff](../../../handoffs/noel-biju.md).

The billing UI has 38 billing/payment-command/picker tests
covering server money/pagination, roles, field errors, durable scoped payment
recovery across navigation/reload, uncertain replay failures, paid recovery,
rule writes across pending navigation, URL drilldown/history filters and stale reads. These tests use UI
fixtures; the separate live browser check used real persistent billing data.

## Domain boundary

Subscription DTOs supply exactly one BASE line and already variant-adjusted product unit prices. Product tax membership is resolved at each period_start by the catalog helper, while the base-fee stable selection comes from plan_snapshot["tax_rule_ids"]. Billing resolves retained rates, selects one discount and commits its global usage with the invoice.

The shared money helper uses Decimal ROUND_HALF_UP; tax and percentage inputs support at most four fractional digits. Invoice dates use actual Asia/Kolkata creation date plus payment terms, with original service bounds retained. Replays never reprice or reset dates.

[billing.feature](billing.feature) remains a readable acceptance specification, not an installed BDD runner. [CONCURRENCY.md](CONCURRENCY.md) records the real PostgreSQL protocol and joint lifecycle evidence. Gherkin text or sequential duplicate calls are not race-test evidence.

Mailpit invoice SMTP/web-inbox capture is verified locally. External delivery is explicitly deferred by the user until real SMTP is configured. Credentials and private recipients never belong in fixtures or public evidence.

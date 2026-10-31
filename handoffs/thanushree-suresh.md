# Thanushree Suresh: handoff

Status: CALENDAR AND PERSISTENT BILLING INPUTS VERIFIED; WORKFLOWS/API/UI IN PROGRESS

Role: Subscription Workflows
Branch: feature/subscription-lifecycle
Reviewed Gate A main: 5b7856792780b38823d90a8fb01e2cdff82f22f2
Getter implementation commit: a40fe5ade884f5d765fe1f05ee1df22ad70c7bdb
Calendar implementation: bdb1cf29447ca9d7303d27e049dd61ac31ad6214 (integrated in PR #1)
Carried audit regressions: 6db99a6 (original dbbbeb0 remains on the prior branch)

## Delivered behavior

The calendar preserves original daily/weekly/monthly/yearly anchors, caps exclusive
service ends and closure dates, and handles exhausted or very large cycle indices.
The persistent getter reads only the next unprocessed ACTIVE subscription cycle,
returns one BASE line plus already-priced product lines, resolves product tax
identities for each period start and preserves frozen plan/product prices. It
never creates an invoice/period, advances a cursor, selects rates/discounts or commits.

DTOs and nested snapshots are copied into immutable mappings/tuples. The explicit
snapshot_to_json helper materializes fresh JSON dictionaries/lists for billing's
invoice persistence. Base-fee tax IDs come from plan_snapshot.tax_rule_ids; product
memberships use Catalog.get_product_tax_ids. Due-date checks belong to the worker.

Prepared lifecycle inventory: 71 expanded cases. Those scenarios remain unbound;
their presence is not proof of implemented lifecycle/API/browser behavior.

## Implemented interfaces

app.modules.subscriptions.calendar exports CycleSnapshot and get_cycle_bounds.
app.modules.subscriptions.service exports BillableInputs, BillableLine,
get_billable_inputs(db, subscription_id, cycle_index), and snapshot_to_json(value).

BillableInputs fields: subscription_id, customer_id, revision, plan_id, currency,
payment_terms_days, cycle_index, period_start, period_end, effective_end, paused,
plan_snapshot, lines. BillableLine fields: stable_line_key, product_id, variant_id,
description, quantity, unit_price (Decimal), selected_tax_ids (UUID tuple),
source_snapshot. BASE has quantity 1; product unit_price already includes variant
adjustment. Snapshot mappings are read-only: call snapshot_to_json before JSONB writes.

Caller contract: hold the subscription row lock and own the transaction; reuse
persisted period outcomes before asking for mutable current inputs. Negative or
noninteger indices are INVALID_CYCLE/409 before lookup. Missing record is 404;
non-ACTIVE, earlier/future cursor and exhausted periods follow docs/05 error codes.

## Checks actually run

Against the getter implementation and this workspace's isolated native PostgreSQL
test database cadentra_subscriptions_test, with DATABASE_URL/TEST_DATABASE_URL set
locally and Python 3.12.13 from the pinned foundation environment:

- backend/.venv/bin/python -m pytest backend/tests/subscriptions/test_billable_inputs.py -q:
  25 passed (including independent JSON materialization added after the 24-case first run).
- backend/.venv/bin/python -m pytest backend/tests -q: 99 passed, 121 subtests passed.
- backend/.venv/bin/ruff check backend scripts/smoke.py: PASS.
- Ruff format/check for new service and test files: PASS.
- python3 scripts/check_pack.py and git diff --check: PASS.
- Independent standards and specification reviews: no blocking findings.
- Getter tests first failed collection before service.py existed, then passed
  against actual models/catalog helpers and PostgreSQL; no missing-service skips.
- Calendar: 10 tests passed on both the original host and foundation Python 3.12.
- Shared frontend baseline: typecheck, lint, 47 unit tests and build passed locally.

Database fixtures roll back their work; tests use only agent-2's isolated test
DB. No migrations, shared models, dependency manifests, other feature code or
another contributor's handoff were edited by this slice.

## Current work and remaining acceptance

Persistent templates, draft/quotation/confirmation/activation, policy actions,
worker lifecycle integration, safe customer query/action services and staff UI
are being implemented in owned paths. T10-T13, T33-T34, cross-customer T06 and
integrated browser T31 still need actual service/API/browser evidence. Financial
concurrency remains a joint integration check with Noel Biju. No deployment or
external email delivery is claimed.

Gate A is released and incorporated, with migrations 0001/0002 and shared imports.
No additional model or migration change is requested. Schema needs, if discovered,
will be sent to Midhun P M with type/nullability/default/rationale. Frozen contracts
remain coordinator-owned; docs/05 and docs/06 are authoritative.

## Git and integration

SSH gh-agent2 authenticated thanushreesuresh and pushes use that key with
IdentitiesOnly. Existing global credentials and author configuration are preserved.
The available CLI/API login is 9MidhunPM, so Midhun P M creates the prepared PR.
Previous subscription PR #1 is merged. Current branch incorporates reviewed main
without rebasing shared history; keep atomic commits at most 30 minutes apart
while active and refresh/incorporate reviewed main at least hourly. Coordinator
serializes tested PR integration; do not bypass checks to meet a checkpoint.

## Prepared PR

Title: Expose immutable subscription period inputs for billing
Target: main
Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-lifecycle

Description: Read the next unprocessed subscription cycle through immutable
pricing inputs, preserving frozen prices and original calendar bounds while
resolving product-tax memberships per service period. Provide explicit JSON
materialization for invoice snapshots. Real PostgreSQL contract tests and the
full backend suite pass. Lifecycle/API/UI work remains in progress and is not
claimed by this getter slice.

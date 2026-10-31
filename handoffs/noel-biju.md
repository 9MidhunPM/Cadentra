# Noel Biju: handoff

Status: FINANCIAL API INTEGRATED; TRANSACTIONAL ISSUER READY; BILLING UI UNDER FINAL REVIEW

Role: Billing & Payments
Branch: feature/billing-period-runtime
Reviewed baseline: 0b257c8 (Gate A, immutable getter, financial API, privacy/fixture fixes)
Issuer implementation: 41dffac6a826930198e53242ed3b5e0e94cd619e

## Delivered and integrated

- Setup ca07fe256f66147fa8baca0bd40649e6c690f19f verified the existing noel-ult author and gh-agent3 SSH account and pushed the requested initial test checkpoint.
- Pricing d380643f4b1b4d844d4bc51f66d70c8f24498532 and precision fix 9d7ebc2ba4c5327a81443005f5d6f843fdcc60ef calculate immutable Decimal results against all 15 vectors. Shared money helper is now adopted.
- Financial API 7fb055d305b782a458929696543c9cc529f66019 implements retained tax/discount revisions, permission-checked invoice queries/actions, idempotent manual payments, queued email and escaped print.
- Privacy 73cdbcccb88b364ceacdb7e53a3d8d10e57f26a9 explicitly whitelists public party/address scalars; nested private fields cannot pass through customer DTOs or print reuse.
- Fixture fix 5d8ce044e19f1f0bdbec00ab37b88c7a77ce35ef removes only its generated invoice-race UUID graph from an explicitly disposable test database.

These slices went through coordinator-created PRs, preserving actual commit authors. No global authentication or identity settings changed. All pushes use the verified gh-agent3 SSH key.

## Ready issuer slice

The issuer locks each subscription, reuses durable outcomes before requesting current inputs, and commits period, invoice/line/tax snapshots, redemption/counter and financial cursor together. Paused periods receive durable PAUSED outcomes. Cancelled periods are never automatically replaced.

Bounded batches count failed attempts and persist traversal continuation in append-only BILLING_BATCH audit records, as approved by Midhun P M. Traversal wraps once and survives process restart; it is separate from next_cycle_index. Failed financial periods remain unresolved and discoverable.

Tax revisions are evaluated at period_start. Product memberships come from Catalog.get_product_tax_ids through the subscription getter, without repricing; the base fee keeps the explicit stable IDs in plan_snapshot["tax_rule_ids"]. Inputs contain exactly one BASE line and already variant-adjusted product unit prices.

Invoice creation uses the shared business clock, preserving original service periods. Due date adds payment terms to actual issue date; replay/confirmation does not reset stored dates. Public run-due accepts no as_of, limit or authoritative money overrides.

## Owned files

Implementation: backend/app/modules/billing/ (pricing, rules, invoices, issuance, router and stable service exports).
Tests: backend/tests/billing/ (actual pricing/rule/invoice/issuance/API/race tests plus prepared reference assets).
UI: frontend/src/features/billing/ is implemented in the working tree and remains outside this issuer commit until final review is complete.
Handoff: handoffs/noel-biju.md.

No shared models, migrations, dependency manifests, central frontend routes or other owners' handoffs were edited.

## Tests actually executed

- Planning-pack/reference checks passed; these are not application verification.
- Actual pricing suite: 13 tests, including 15 vectors, per-tax rounding, stable-key allocation, immutability, ambient precision and invalid/storage-bound values.
- Rules: 22 actual PostgreSQL/API tests passed, covering admin-only writes, retained revisions, minimums, caps, scopes, date windows and zero-benefit selection.
- Invoice/payment tests: 14 actual PostgreSQL tests passed after the privacy/fixture patch, including three genuine two-connection payment capacity/replay/cancellation races, zero-total confirmation, partial/full settlement, overpayment/date/key conflicts, print, CSRF/roles and outbox deduplication.
- Issuance: 9 actual PostgreSQL tests passed. They cover golden snapshots/dates/replay, full charge for shortened periods, flushed-before-commit rollback/retry, two independent connections for same-period issuance and the last capped discount use, paused catch-up, actual SQLSTATE 23505 rollback/reload and bounded-failure progress in a fresh interpreter.
- Full backend: 146 tests and 121 subtests passed from a fresh generated UUID schema migrated to the reviewed Alembic head. Previously retained public test rows were left untouched. Each committed issuance fixture migrates and drops only its own generated schema after workers finish; no public truncation, database drops or disabled integrity triggers.
- Run-due HTTP tests verify real role/CSRF guards, strict empty payloads and server-owned clock/batch size.
- Ruff, Python compilation and whitespace checks passed for the reviewed backend slices. Independent standards/specification review findings on batch limits and starvation were corrected before the issuer commit.

Exact normal test command with isolated PostgreSQL environment:
`backend/.venv/bin/pytest backend/tests/billing -q`.
Full-suite command inside the clean migrated-schema harness:
`backend/.venv/bin/pytest backend/tests -q`.

Canonical subtotal 4680.00, discount 468.00, tax 758.16, total 4970.16.
Payments 2000.00 and 2970.16 leave balances 2970.16 and 0.00.
The cap race creates one 4970.16 invoice and one undiscounted 5522.40 invoice, with one redemption/counter increment. Same-period contention creates exactly one period and invoice.

## Native/browser and mail evidence

Own Python 3.12.13 environment and isolated PostgreSQL 18.6 application/test databases are verified at migration 0002. Docker is absent in this shell.

Actual Chromium desktop/mobile billing flow passed against the API and persistent ACTIVE-subscription fixture: create 18% product tax and 10% discount, run due, confirm, record the canonical two payments, reload Paid/zero balance, queue email, print and verify staff read-only rules. No relevant console/page errors, framework overlays or page overflow were observed. This is billing from a prepared ACTIVE fixture, not a claim that the full catalog/lifecycle journey ran.

The actual invoice outbox dispatch reported processed=1, accepted_by_smtp=1, failed=0. The message appeared in the native local Mailpit web inbox with the correct invoice number, total, paid amount and balance. Only fictional recipients were used in visual fixtures. Evidence/scripts/screenshots stay under /tmp, outside the public repository.

User explicitly deferred external delivery until a real SMTP provider is configured. Real SMTP remains environment-configurable with no committed credentials. Midhun P M owns Compose/Mailpit/standalone-outbox wiring and password-reset verification. Native capture is verified; Docker Compose execution is not claimed.

## Stable interfaces

- app.modules.billing.service.get_invoice_for_actor(db, actor, invoice_id) returns plain safe JSON-ready detail.
- render_invoice_for_actor(db, actor, invoice_id) returns escaped printable HTML.
- list_invoices_for_actor(db, actor, ...) returns the normal paginated envelope.
- CUSTOMER actors can use these helpers only for their own records; foreign IDs return 404. Staff routes remain ADMIN/STAFF only.
- CONFIRMED collection labels are UNPAID or PARTIALLY_PAID; PAID/DRAFT/CANCELLED remain their status, and overdue is a separate boolean.
- run_due(session_factory, as_of, limit) is the worker interface. Optional actor context attributes an explicit staff run; financial operations own their transactions.
- Email requests return 202/outbox status. SENT means SMTP acceptance, not verified external delivery.

## Remaining work and integration needs

Publish/integrate the ready issuer, finish the billing UI review fixes and commit its tests. Joint T13/T34 worker/lifecycle closure and billing-versus-policy race verification awaits the reviewed subscription action service. Coordinate the complete persisted browser journey and performance evidence with Sherin Saji. Do not mark the whole billing workstream complete from arithmetic or API tests alone.

Keep atomic active-work commits no more than 30 minutes apart. Incorporate reviewed main at least hourly and send exact tested heads to Midhun P M. SSH-only pushes remain selected; the coordinator creates/reviews/merges PRs through its existing account.

## Prepared issuer PR

Title: Issue recurring invoices atomically with bounded fair catch-up

Create exactly one durable outcome per subscription cycle, preserving immutable prices/taxes/discounts and safe retries. Bound work including failures, retain fair traversal progress across restarts, and expose the authenticated run-due action through the shared clock.

Validation: 9 actual PostgreSQL issuance tests, 2 HTTP boundary tests, the clean-schema 146-test backend run, Ruff and independent reviews passed. Billing UI, joint full lifecycle/worker/browser verification and performance are separate remaining slices.

Target main: https://github.com/9MidhunPM/Cadentra/compare/main...feature/billing-period-runtime

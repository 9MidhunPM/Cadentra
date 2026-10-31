# Noel Biju: handoff

Status: BILLING CORE INTEGRATED; URL DRILLDOWN CORRECTION READY; FINAL T31/T30 CHECKS OPEN

Role: Billing & Payments
Branch: feature/billing-integration-proof
Reviewed main incorporated: 6cd8b7467698520f8fb1fddb22c353e827dc8082 (corrected billing UI PR #13, issuer, subscription actions, joint worker/race tests, catalog search and local mail wiring)
Issuer implementation: 41dffac6a826930198e53242ed3b5e0e94cd619e
Published issuer review head: 96b2a85b19207bf3772574b9c11bdecab577ad74
Controlled invoice-race extension: 45c7465 (preserved from 7ca967f on the prior branch)
Initial UI review head: 3076a16c3356de9360c9932b42ca9b885b9d6411 (held for corrections; superseded by the final review head)
Discount boundary tests: e0f0e59
Historical invoice/cancellation proof: 1a7314e
Paginated product picker: 6da4116
Payment recovery correction: d18c3e121c61d1662e680117147b0f4def6d4fb1
Final UI review head: 5037de083b7da163e12571c749941d75c92ab3a6 (merged through PR #13)
Invoice URL drilldown correction: 695c67de08d2a380c3ba356d8987e9d049a46f0e (reviewed baseline 18e88ff)

## Delivered and integrated

- Setup ca07fe256f66147fa8baca0bd40649e6c690f19f verified the existing noel-ult author and gh-agent3 SSH account and pushed the requested initial test checkpoint.
- Pricing d380643f4b1b4d844d4bc51f66d70c8f24498532 and precision fix 9d7ebc2ba4c5327a81443005f5d6f843fdcc60ef calculate immutable Decimal results against all 15 vectors. Shared money helper is now adopted.
- Financial API 7fb055d305b782a458929696543c9cc529f66019 implements retained tax/discount revisions, permission-checked invoice queries/actions, idempotent manual payments, queued email and escaped print.
- Privacy 73cdbcccb88b364ceacdb7e53a3d8d10e57f26a9 explicitly whitelists public party/address scalars; nested private fields cannot pass through customer DTOs or print reuse.
- Fixture fix 5d8ce044e19f1f0bdbec00ab37b88c7a77ce35ef removes only its generated invoice-race UUID graph from an explicitly disposable test database.

These slices went through coordinator-created PRs, preserving actual commit authors. No global authentication or identity settings changed. All pushes use the verified gh-agent3 SSH key.

## Integrated issuer

The issuer locks each subscription, reuses durable outcomes before requesting current inputs, and commits period, invoice/line/tax snapshots, redemption/counter and financial cursor together. Paused periods receive durable PAUSED outcomes. Cancelled periods are never automatically replaced.

Bounded batches count failed attempts and persist traversal continuation in append-only BILLING_BATCH audit records, as approved by Midhun P M. Traversal wraps once and survives process restart; it is separate from next_cycle_index. Failed financial periods remain unresolved and discoverable.

Tax revisions are evaluated at period_start. Product memberships come from Catalog.get_product_tax_ids through the subscription getter, without repricing; the base fee keeps the explicit stable IDs in plan_snapshot["tax_rule_ids"]. Inputs contain exactly one BASE line and already variant-adjusted product unit prices.

Invoice creation uses the shared business clock, preserving original service periods. Due date adds payment terms to actual issue date; replay/confirmation does not reset stored dates. Public run-due accepts no as_of, limit or authoritative money overrides.

## Owned files

Implementation: backend/app/modules/billing/ (pricing, rules, invoices, issuance, router and stable service exports).
Tests: backend/tests/billing/ (actual pricing/rule/invoice/issuance/API/race tests plus prepared reference assets).
UI: frontend/src/features/billing/ is implemented and independently reviewed, remaining a separate slice from the issuer PR.
Handoff: handoffs/noel-biju.md.

No shared models, migrations, dependency manifests, central frontend routes or other owners' handoffs were edited.

## Tests actually executed

- Planning-pack/reference checks passed; these are not application verification.
- Actual pricing suite: 13 tests, including 15 vectors, per-tax rounding, stable-key allocation, immutability, ambient precision and invalid/storage-bound values.
- Rules: 30 actual PostgreSQL/API tests passed, covering admin-only writes, retained revisions, minimums, caps, scopes, date windows and zero-benefit selection. The eight new cases directly prove inclusive starts, exclusive ends, future/expired discounts and below/exact/above minimum eligible product gross while preserving usage counters.
- Invoice/payment tests: 11 PostgreSQL/API cases and eight controlled two-connection races passed, covering zero-total confirmation, partial/full settlement, overpayment/date/key conflicts, print, CSRF/roles, outbox deduplication and both lock orders.
- Issuance: 10 actual PostgreSQL tests passed. They cover golden snapshots/dates/replay, full charge for shortened periods, flushed-before-commit rollback/retry, two independent connections for same-period issuance and the last capped discount use, paused catch-up, actual SQLSTATE 23505 rollback/reload and bounded-failure progress in a fresh interpreter. A real retained tax revision followed by advanced-clock replay, confirmation, detail and print preserves the original rate, total and dates. Issued discounted cancellation plus replay/run-due preserves one cancelled invoice, period, redemption and consumed use.
- Final combined backend: 329 tests and 121 subtests passed in 64.74 seconds at source HEAD deecddb, including reviewed main beedbbd, on 2026-10-31. A fresh outer generated UUID schema migrated to 0002 and was removed after workers joined; pre-existing public user/customer/period/invoice/payment counts remained exactly unchanged. Per-test issuance schemas are likewise generated and removed. No public truncation, database drops or disabled integrity triggers.
- Eight controlled invoice races passed: both acquisition orders for payment capacity, matching payment replay, payment versus cancellation, and matching sends. A third physical connection proves the loser waits on PostgreSQL's actual row lock before the winner is released.
- Billing UI: 38 owned billing/payment-command/picker cases pass, including eight URL-filter regressions. Independent reviews cleared payment navigation/reload retention, failed replay uncertainty, paid-invoice recovery, late outcomes, stale read reconciliation, route state, zero usage caps, product pagination and invoice query state. Fixture tests are separate from the live persistent browser evidence below.
- Full frontend: 151 tests in 13 files, typecheck, lint, production build and whitespace checks passed after the URL correction. The existing bundle-size warning remains nonblocking; no new dependency was added.
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

The corrected payment recovery probe committed one fictional local manual ledger entry for 2000.00, deliberately lost its HTTP acknowledgement, navigated away/back, reloaded and retried the same body/key. Actual API history held exactly one payment and balance 2970.16. No gateway, bank or funds transfer was involved. Retention is scoped by actor and invoice, saved before POST in sessionStorage, and cleared only after matching fresh payment history. Failed uncertain replays retain their key even after authentication/validation errors. Paid invoices expose recovery without accepting new payments.

A separate read-only live Paid recovery check reloaded a retained existing payment, verified it through fresh history and cleared the recovery shell/storage with zero ledger writes, zero page errors and the original invoice unchanged.

Actual catalog/picker verification used 105 fictional products: pages of 100 and five, exact search returning one, retained selection names across page/search changes, zero rule writes and zero page errors. The coordinator's bounded name-search API is integrated.

T30 preparation found that the initial invoice list ignored overdue/customer URL parameters. The correction makes known URL filters and page authoritative, keeps them in controls and browser history, resets page on filter changes and forwards only allowed API parameters. Actual read-only QA showed two invoices unfiltered versus zero overdue, retained the customer when clearing collection, and restored filtering through Back/Forward with zero domain writes or page errors.

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

Issuer PR #12 is integrated. Joint T13/T33/T34 verification is integrated through PR #14 and passed in the combined run: four actual worker cases and six controlled billing-versus-edit/pause/close races, including both lock orders with three physical connections and observed database blocking. Downtime drains eligible history before closure, PAUSED outcomes remain explicit, shortened cycles retain full pricing and earlier invoice snapshots survive future policy changes. Midhun P M separately verified two actual standalone worker processes creating one due invoice then preserving IDs/snapshots/counts on restart.

The completion audit's three own-scope evidence gaps are closed by the focused PostgreSQL tests above. Coordinator review of the initial UI found payment command loss across navigation and an unreachable product-picker page. Both were corrected and independently re-reviewed before the final UI head.

The payment/picker UI is integrated through PR #13. The URL drilldown correction is ready for coordinator review and serialized integration; it must be included before final overdue-page measurements. Sherin Saji owns the full persisted T31 browser journey and actual billing-page T30 measurements. The earlier performance benchmark explicitly excluded placeholder staff billing surfaces; it does not count as those measurements. Resolve any further billing defects these gates reveal before marking the workstream complete.

Keep atomic active-work commits no more than 30 minutes apart. Incorporate reviewed main at least hourly and send exact tested heads to Midhun P M. The coordinator's latest workflow instruction is owner SSH integration after code review and an explicit serialized go-ahead, with no new GitHub API/PR merge operations. Preserve historical PR records and original authorship; never force-push.

## PR review

Issuer PR: https://github.com/9MidhunPM/Cadentra/pull/12 (merged)

UI PR: https://github.com/9MidhunPM/Cadentra/pull/13 (merged)

Title: Add persistent invoice, payment and rule workspaces

Replace billing placeholders with server-backed invoice filters/detail, due billing, confirm/cancel/send/print, durable manual-payment recovery and administrator retained-rule forms. Preserve uncertain payment bodies/keys across navigation and reload until fresh history verifies them, including recovery on paid invoices. Guard pending/uncertain rule writes across navigation; browse/search all product pages while retaining selections. Staff rule views remain read-only. Includes controlled invoice-lock races, discount boundary tests and historical invoice proofs.

UI comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/billing-workspace

# Thanushree Suresh: handoff

Status: SUBSCRIPTION WORKFLOWS/API/STAFF UI IMPLEMENTED; JOINT INTEGRATION AUDIT OPEN

Role: Subscription Workflows
Branch: feature/subscription-integration
Reviewed main incorporated: 382fa2b69035e86bf928cb879349cc2d3440dc1b (PRs #11/#12 merged)
Backend workflow/API commit: f8fa86715ad607936fbec559a198f7ed2eb9abb4
Staff UI commit: 58fbb5f6f634a0da842a2beac952675174050941
Projection privacy fix: f6acf92b6e35a49a29c9f292cc4216ffdcceecc1
Frozen policy verification: 2d61b8d51a45a2df13edb8a868950046ca887a76
Named template plan labels: c046593f7e91b9fdd58f0b2d16dbd863988fdae5
Lifecycle/availability boundary coverage: 3f759740b2196f3d8973ba5798214d85d18f3980
Actual worker/action race verification: a9817959c5af35b06b5d1eecdf3279974423334a
Prior getter implementation a40fe5a and calendar bdb1cf2 were integrated in PRs #6/#1.

## Delivered behavior

Templates and copied drafts persist plan/lines/validity. Explicit line arrays
replace template lines; null/empty overrides fail validation. Template copies
serialize with edits under a refreshed row lock. Quotation validity survives
reload and later template edits. Explicit issue days update the copied default.

Draft -> Quotation -> Confirmed -> Active -> Closed is enforced. Confirmation
rejects changed quoted plan price, cadence, quantity, policies or selected plan
tax IDs with QUOTATION_PLAN_CHANGED/409; staff revise/reissue rather than silently
accept changed terms. Product prices stay frozen until revision/reissue.

Pause/resume/early-close/expiry/linked renewal and next-cycle line changes enforce
frozen plan flags and customer ownership. Due periods block repricing/schedule
changes. Exhausted periods cannot accept next-cycle edits or a false resume at
expiry. Pending unapplied pauses can be cancelled with an audit; started/processed
pause history remains intact. Lifecycle processing activates eligible records and
defers final closure until earlier periods have durable outcomes. All mutations
use caller-owned transactions, subscription row locks and redacted audits.

Staff screens use actual APIs and shared routing/client/UI: paginated/filterable
lists, template creation/editing, multi-line drafts and variants, quotations,
confirmation disclosure, lifecycle controls, renewal and active line edits.
Server errors preserve form values. Dates and effective changes are explicit.
Line amounts and period-specific tax references come from the backend; the client
never calculates invoice totals. Invoice references link to billing records.

## Interfaces for billing and customer portal

app.modules.subscriptions.calendar exports frozen CycleSnapshot and get_cycle_bounds.
app.modules.subscriptions.service exports BillableInputs, BillableLine,
get_billable_inputs, snapshot_to_json, get_subscription_for_actor, apply_action,
and process_lifecycle. Query/action facades return a raw safe detail dictionary;
HTTP wrappers add the data envelope.

- Billing owns the subscription lock and transaction, reuses durable period
  outcomes first, and requests only next_cycle_index. Inputs contain one BASE
  line (quantity 1) and already-adjusted product prices, UUID tax-ID tuples and
  recursively immutable source snapshots. snapshot_to_json returns independent
  JSON dictionaries/lists for invoice persistence. No getter commits or reprices.
- Portal writes use with db.begin(): apply_action(db, actor, id, action, payload).
  The service rechecks ownership/policy and validates payloads. Customer actions
  are limited to pause/resume/close/renew; renew returns a linked DRAFT only.
- Safe detail includes allowed_actions, paused, pause_interval, pause_effective_on,
  resume_effective_on, close_effective_on, prior_subscription_id, quotation_valid_days,
  next_billing_date, public plan/lines, server line_total and invoice_references.
  Taxes are metadata previews at tax_preview_on; final invoice snapshots remain
  authoritative. Read-only rule resolution is delegated to billing.rules.
- Missing and foreign protected records share NOT_FOUND/404 and the message
  Record not found. Public projections constrain field types, remove malformed
  nested metadata and reject invalid or empty financial snapshots with generic
  INVALID_SNAPSHOT/409. Costs and staff-only notes are not returned.

Example authenticated requests (substitute actual IDs; shared CSRF applies):
POST /api/v1/subscriptions/{id}/issue-quotation with {"valid_days":14}
POST /api/v1/subscriptions/{id}/confirm with {}
POST /api/v1/subscriptions/{id}/renew with
{"start_date":"2027-05-01","end_date":"2027-08-01"}
Dates above illustrate a request, not a production clock override.

## Checks actually run

Python 3.12.13; PostgreSQL 18.6; reviewed migrations 0001/0002. The current suite
uses the separate cadentra_subscriptions_integration_test database. The original
workstream test DB and earlier verification DB remain intact. Worker/race fixtures
use independently migrated UUID schemas and remove only those newly created schemas.

- backend/.venv/bin/python -m pytest backend/tests -q:
  314 passed, 121 subtests passed in 59.25s on reviewed main 382fa2b plus this
  integration slice. Includes all 124 subscription cases: 10 calendar,
  25 billing-input, 52 workflow, 27 API, four actual worker and six race cases.
  No missing-service skips. The 13 added guard cases cover future activation,
  terminal-state edits, renewal date constraints, due pause/close guards,
  requested-start availability endpoints and template-plan mismatch.
- Real template copy/edit race uses independent connections and observes an
  actual PostgreSQL lock wait; cached template rows refresh coherently.
- Policy tests cover disabled pause/close/renew for staff and an actual customer
  owner, asserting conflict/no mutation/no misleading action hint.
- npm test: 79 passed across the current shared+feature frontend suite.
- npm run typecheck, npm run lint, npm run build: PASS.
- backend/.venv/bin/ruff check backend scripts/smoke.py: PASS.
- python3 scripts/check_pack.py and git diff --check: PASS.
- Independent standards/specification/UI reviews found issues that were fixed;
  final focused reviews have no remaining blocker in the owned code.
- Coordinator's earlier reviewed PR #11 integration: 280 backend tests,
  121 subtests and 113 frontend tests pass, plus type/lint/build/Ruff/pack/security.
  This combined run was performed by the coordinator, not rerun locally here.

Native Chromium QA used the real API/PostgreSQL at http://127.0.0.1:5172 through
its same-origin proxy (API 8002), at 1440x1000 and 390x844. Browser plugin was not
available; existing Playwright was used. The flow exercised real staff login,
template14 -> draft/reload -> quotation -> acknowledged confirmation -> ACTIVE
and reload, frozen variant price/line amount, tax names/rates, and a rejected
DUE_BILLING_PENDING edit with preserved form input. No page error, blank screen,
framework overlay or page-width overflow; the deliberately exercised 409 is the
only expected console error. Screenshots were inspected. Temporary QA scripts,
reports and screenshots stay outside the repository in /tmp/cadentra-agent2-qa.

## Remaining integration gates and honest limits

The historical broad backend run after billing PR #7 reported 176 passed/8 failed:
the obsolete coordinator-owned subscriptions501 assertion, committed financial
race fixtures polluting global empty-table assumptions, and two owned assertions
that were subsequently made before/after or baseline-relative. The final owned
suite now passes 124 cases within the green full 314-case run in a separate DB.
Root/Noel corrected the shared tests/fixture isolation.
No global truncate, financial-data deletion or database drop was performed.

T09-T13/T33/T34 now have actual service/API/worker/concurrency evidence. The
integration test slice still requires coordinator review/merge. The remaining
full-role verification is joint T31 through invoice creation/payment/customer-portal reload, plus live
   portal ownership isolation. The native staff journey proves only its portion.
No deployment, external email delivery or hardware/performance claim is made.

Actual integrated evidence: four real worker cases and six real billing/action
lock-order cases pass against reviewed main 382fa2b plus this owned test slice.
The worker cases create real subscriptions and invoices, retain historical PAUSED
outcomes and defer closure until backlog is drained. Race tests use three distinct
physical connections, observed PostgreSQL Lock/blocking-PID relationships and both
lock orders for edit/pause/close; historical invoice snapshots/dates remain intact
and only future cycles change. No alternate billing service is used. Each fixture
migrates and removes only its own freshly created UUID schema in the separate
integration test DB. Final standards/specification source reviews found no blocker.
The final integrated run includes all ten cases; no seeded period outcome stands
in for actual billing in these worker/race tests.

## Coordination and PR

SSH-only: push with verified gh-agent2/IdentitiesOnly, preserve real commit author,
and send tested heads to Midhun P M. No gh login, OAuth/token setup or global
account switching. Coordinator creates/reviews/merges PRs using existing auth.
Keep atomic active-work commits within 30 minutes, incorporate reviewed main at
least hourly, and report ready slices sooner. Preserve both earlier feature branches.

Title: Verify subscription lifecycle boundaries and billing integration
Target: main
Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-integration

Description: Verify lifecycle/renewal/availability guards, actual bounded worker
catch-up and both PostgreSQL lock orders for billing versus edit/pause/close.
Assert durable pause history, closure ordering, full final-cycle pricing, retained
debt, immutable past invoices and future-only changes. All 314 backend tests and
121 subtests pass on reviewed main 382fa2b plus this test-only slice; Ruff, pack
and whitespace checks pass. Joint paid-invoice/customer-portal browser verification
remains with the reporting/billing owners and does not block these scoped tests.

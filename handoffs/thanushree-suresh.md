# Thanushree Suresh: handoff

Status: REQUIRED SUBSCRIPTION BEHAVIOR VERIFIED; CURRENT AUDIT FIXES READY FOR REVIEW

Role: Subscription Workflows
Branch: feature/subscription-current-audit
Reviewed integration main: ea9183623a11b1a91fc4e17eedd3d3889f373f33
Runtime-fix commit (check source): c4c0d05511e9702a1850a8a1ddab457880e7471e
Refreshed feature head: 20e271f75e192395dd79aa3a664c189eef5cc5cd;
all owned paths are identical to tested/reviewed bc43dd7. The clean integration
candidate is preserved on feature/subscription-audit-integration.

## Current audit, 31 October 2026

Three concrete defects found on current main are fixed in separate atomic commits:

- b184354: a failed product-variant lookup can be retried in place without losing
  the selected product/variant, quantity, customer, dates or payment terms.
- 18e6134: browser Back/Forward updates the subscription filter controls to match
  the URL and results. Pagination and retry preserve unapplied filter edits.
- c4c0d05: create/edit/renew and quotation confirmation reject payment terms whose
  invoice due date exceeds the supported date range. The coordinator approved the
  horizon max(real business date, service end); there is no arbitrary days cap.
  Billing retains its actual issue-date check for catch-up after that horizon.
  Existing quotations remain recoverable through revise/edit/reissue. No models,
  migrations, lifecycle policy or historical data are changed.

Checks actually run for this slice:

- In backend, APP_ENV=test and DATABASE_URL/TEST_DATABASE_URL pointed to the owned
  cadentra_subscriptions_integration_test PostgreSQL database. `.venv/bin/python
  -m pytest tests/subscriptions/test_workflows.py -q`: 62 passed in 5.42s. The ten
  added cases first reproduced eight missing rejections (two valid boundaries
  already passed), then passed with the fix. They verify no record/audit mutation,
  clock-advanced and legacy quotation correction, and real billing issuance/replay
  at the accepted boundary with due_date=9999-12-31.
- `npm --prefix frontend test -- --run src/features/subscriptions/forms.test.tsx
  src/features/subscriptions/subscriptions.test.tsx`: 18 passed after both new UI
  regressions reproduced their failures. These are component tests with API
  fixtures and a real memory router, not new native browser evidence.
- `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`,
  backend `.venv/bin/ruff check app/modules/subscriptions/workflows.py
  tests/subscriptions/test_workflows.py`, and `git diff --check`: pass.
- Independent read-only reviews of the exact owned backend/UI diffs found no
  blocking issue. The full application suites were not rerun for this slice.

No main-push clearance has been given for this head. Midhun P M owns shared UI
polish, contract recording and deployment; this slice changes only owned feature
code, tests and these two owned evidence documents. No missing migration or shared
runtime dependency is requested.

Historical implementation references (already integrated):

Backend workflow/API commit: f8fa86715ad607936fbec559a198f7ed2eb9abb4
Staff UI commit: 58fbb5f6f634a0da842a2beac952675174050941
Projection privacy fix: f6acf92b6e35a49a29c9f292cc4216ffdcceecc1
Frozen policy verification: 2d61b8d51a45a2df13edb8a868950046ca887a76
Named template plan labels: c046593f7e91b9fdd58f0b2d16dbd863988fdae5
Lifecycle/availability boundary coverage: 3f759740b2196f3d8973ba5798214d85d18f3980
Actual worker/action race verification: a9817959c5af35b06b5d1eecdf3279974423334a
Theme notice contrast fix: a9b7a0c1b9f6b453395565effc1f34457c5079d6
Prior getter implementation a40fe5a and calendar bdb1cf2 were integrated in PRs #6/#1.

## Delivered behavior

Templates and copied drafts persist plan/lines/validity. Explicit line arrays
replace template lines; null/empty overrides fail validation. Template copies
serialize with edits under a refreshed row lock. Quotation validity survives
reload and later template edits. Explicit issue days update the copied default.
Coordinator clarification: the role's "Template CRUD" shorthand means the frozen
GET/POST/PATCH create/read/update scope. The source brief does not require deletion
or archival. No implicit DELETE/archive API or UI was added.

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

## Historical checks actually run

Python 3.12.13; PostgreSQL 18.6; reviewed migrations 0001/0002. The historical suite
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
- Final frontend run on reviewed beedbbd plus the theme correction: 113 tests
  passed across ten files. Typecheck, lint and production build passed. The shared
  bundle-size advisory remains a build warning, not a failure or performance claim.
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

Final post-ACTIVE native QA used the same origin/proxy and viewport sizes with
reviewed beedbbd plus the owned theme fix, in the separate
cadentra_subscriptions_staff_qa_test database. It exercised the actual recurring
issuer for the first due cycle, then staff next-cycle quantity edit/reload while
the issued invoice retained its original amount/lines. Scheduled pause displayed
2026-11-30 and survived reload; resume cancelled that pending pause; early close
displayed the same effective date and retained ACTIVE until the boundary; renewal
navigated to a new linked DRAFT and preserved it on reload without reopening the
old term or changing the invoice. The template table displayed the human plan name.

Screenshot inspection caught hardcoded light notice backgrounds inheriting pale
dark-mode text. The scoped CSS correction uses shared semantic colors for notices,
labels, links, errors and borders. Repeated actual dark/light desktop/mobile QA
passed; computed notice text contrast was 7.96:1 dark and 10.88:1 light. No page
errors, blank state, overlay or page-width overflow; the deliberately rejected
due edit is the only expected 409 console message. Corrected screenshots were
inspected. Private temporary scripts, report.json, close-desktop.png,
close-light-desktop.png, mobile.png and mobile-light.png are under
/tmp/cadentra-agent2-lifecycle-qa. They are not submission fixtures or credentials.

## Joint acceptance evidence and delivery limits

Joint T31 is complete in the retained owner-run evidence:
backend/tests/reporting/evidence/t31-2026-10-31.json. It records a clean unchanged
41ef6df0521d853348803cd71471d5852b7bc313 start/end and one passing Chromium journey
at 06:50 UTC on 31 October. The actual UI/API/database journey reaches Paid after
2000.00 + 2970.16 payments on a 4970.16 invoice, retains zero balance on reload,
reconciles reporting, and verifies portal reload/print, pause/cancel/close/renewal
and cross-customer 404/no mutation. Billing replay creates zero new invoices.
The shared evidence writer and sanitized result were published by Sherin Saji in
471808e69c2760571086ad6d6880ef03ff21eb82 and integrated into main. This is retained
evidence on its recorded source, not a rerun of the current audit head.

Current delivery work is exact coordinator review and serialized integration of
the new audit commits. No current main GO is implied by earlier clearances. The
previous final-document integration candidate remains preserved on its feature
branch; it was not pushed to main after automatic approval review rejected that
main update for lack of direct current-thread user authorization. Do not retry
that stale candidate. Deployment, external email delivery and T30 performance
remain with their respective owners; no new claim about them is made here.

Historical integration diagnosis:

The historical broad backend run after billing PR #7 reported 176 passed/8 failed:
the obsolete coordinator-owned subscriptions501 assertion, committed financial
race fixtures polluting global empty-table assumptions, and two owned assertions
that were subsequently made before/after or baseline-relative. The final owned
suite now passes 124 cases within the green full 314-case run in a separate DB.
Root/Noel corrected the shared tests/fixture isolation.
No global truncate, financial-data deletion or database drop was performed.

T09-T13/T33/T34 have actual service/API/worker/concurrency evidence. PR #14 merged
at 209fef8a35d880133f6c011ab6357b5c7ea02502. The native staff QA below and retained
joint T31 evidence above cover distinct parts of the required journey.

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

## Coordination

SSH-only: push with verified gh-agent2/IdentitiesOnly, preserve real commit author,
and send tested heads to Midhun P M. No gh login, OAuth/token setup or global
account switching. Send the immutable head and expected main to Midhun P M for
exact review and serialized GO before owner-operated local integration. No PR/API
integration or coordinator publication on the owner's behalf is requested.
Keep atomic active-work commits within 30 minutes, incorporate reviewed main at
least hourly, and report ready slices sooner. Preserve both earlier feature branches.

Historical acceptance slice: Keep subscription notices readable across themes
Target: main
Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-acceptance

Description: Replace hardcoded subscription colors that made effective-date and
tax notices unreadable in dark mode with existing semantic theme colors. Native
staff pause/resume/close/renewal and next-cycle edit/reload checks pass against the
real API/PostgreSQL at desktop/mobile sizes in both themes; notice contrast is
7.96:1 dark and 10.88:1 light. All 113 frontend tests, typecheck, lint and build
pass. Only the owned stylesheet and its evidence handoff changed in that slice;
joint T31 was subsequently completed as recorded above.

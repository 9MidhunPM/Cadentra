# Thanushree Suresh: handoff

## Deadline checkpoint: 31 October 2026

The prepared subscription source head `1f27706bd9ac4e121a79a7cece2c91fdce4747d5`
is published on `feature/subscription-threefix-refresh` and is an ancestor of
verified main `059e40cf62d7d33de6349f66f0ef08acf7651a20`. The worktree was
clean at the checkpoint; no subscription code is left uncommitted here. This
handoff-only update follows that source head on the feature branch.

Remaining verification limits: no full backend or frontend suite was rerun for
the refreshed three-fix slice; the recorded focused evidence below is unchanged.
No new checks or deployment verification were performed for this checkpoint.
Other project-wide acceptance and deployment work remains with its owners.

Status: REQUIRED SUBSCRIPTION BEHAVIOR VERIFIED; THREE AUDIT FIXES INTEGRATED

Role: Subscription Workflows
Current candidate branch: `feature/subscription-threefix-refresh`
Reviewed integration baseline: `71af9f6` (demo-history adapter is already integrated)
Current three-fix source commit: `7de8c0e`

## Three subscription fixes refreshed on current main (31 October 2026)

The refreshed branch contains only six owned runtime/test paths plus this handoff
and `backend/tests/subscriptions/README.md`. The six runtime/test files are
byte-identical to the previously reviewed `5324c16` source/tests; root's later
demo clock, importer, UI and deployment updates remain intact. This candidate is
based on `71af9f6`, not the older `ef3097d` approval window.

- Variant lookup has an explicit in-place retry that preserves the product,
  variant, quantity and other draft form inputs.
- Applied subscription filters now follow browser Back/Forward, while page
  navigation and retries preserve unapplied input edits.
- Payment terms are rejected before draft creation/edit/renewal and quotation
  confirmation when their due dates exceed the supported calendar range. The
  check uses the coordinator-approved `max(today, end_date)` horizon; billing
  still validates the actual issue date for later catch-up.

Checks actually rerun on the refreshed runtime tree, using the disposable
`cadentra_subscriptions_integration_test` database:

- Backend `tests/subscriptions/test_workflows.py`: 62 passed in 5.42s.
- Frontend `forms.test.tsx` and `subscriptions.test.tsx`: 18 passed.
- Ruff on the changed workflow/tests and `git diff --check`: pass.
- No full backend/frontend suite was rerun for this refreshed candidate. The
  source/test files are unchanged from the previously reviewed slice.

Exact pre-docs refreshed runtime commits are `81f1082` (variant retry), `1934fdb`
(history filters), and `7de8c0e` (payment-term guard). The earlier review and
approval hold was resolved; the refreshed source is now present in main.

## Targeted demo-history adapter (integrated 31 October 2026)

The owned adapter was developed on `feature/subscription-demo-history`, based on
`ef3097d71d591a52d12e3c6b18089d470b98308b`, and integrated into main at
`6984150fea882b54998c751ee92202d3d7fee48e`.
The owned adapter is `backend/app/modules/subscriptions/demo_import.py`.
`create_or_resume(factory, actor, scenario, created_on=..., at_date=...)` creates
only a marked DRAFT or resumes that exact subscription. `apply_targeted_action`
applies one dated lifecycle action to a marked row; the root importer sequences
events and calls billing for only that subscription. Renewal can attach a second
stable scenario marker to the linked draft in the same transaction.

The marker stores the canonical full intent and SHA-256. Reordered equivalent
lines compare canonically; changed terms, line quantities or scenario targets fail
closed. A transaction-scoped advisory key lock prevents duplicate scenario
creation. Each lifecycle action stores a stable event key and payload hash in the
same transaction, so replay resumes without applying the action twice. The adapter
does not run a global lifecycle scan, billing batch, worker or email outbox.

Four focused PostgreSQL tests passed against the disposable
`cadentra_subscriptions_integration_test` database:
`APP_ENV=test DATABASE_URL=postgresql+psycopg://cadentra@127.0.0.1:55431/cadentra_subscriptions_integration_test TEST_DATABASE_URL=postgresql+psycopg://cadentra@127.0.0.1:55431/cadentra_subscriptions_integration_test backend/.venv/bin/python -m pytest backend/tests/subscriptions/test_demo_import.py -q`.
They cover canonical intent/resume, changed-intent rejection, idempotent quote and
confirmation, linked renewal replay, real targeted invoice and PAUSED outcome,
and expiry closure. Ruff passes for the adapter and its tests. The caller-provided
`at_date` context is the coordinator-owned historical clock; this adapter does
not change the global clock. The catalog, customers, target mix, source
attribution and root CLI orchestration remain Midhun P M's scope.

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

## Historical integration diagnosis and evidence limits

The historical broad backend run after billing PR #7 reported 176 passed/8 failed:
the obsolete coordinator-owned subscriptions501 assertion, committed financial
race fixtures polluting global empty-table assumptions, and two owned assertions
that were subsequently made before/after or baseline-relative. The final owned
suite now passes 124 cases within the green full 314-case run in a separate DB.
Root/Noel corrected the shared tests/fixture isolation.
No global truncate, financial-data deletion or database drop was performed.

T09-T13/T33/T34 have actual service/API/worker/concurrency evidence. PR #14
merged at 209fef8a35d880133f6c011ab6357b5c7ea02502. The former T31 integration
gap was subsequently closed by the retained owner-run evidence at
`backend/tests/reporting/evidence/t31-2026-10-31.json`; it records the clean
41ef6df source and paid invoice/reload, reporting, portal lifecycle and ownership
checks. It is retained evidence, not a rerun on the refreshed three-fix candidate.
Deployment, external delivery and hardware/performance claims remain with their
respective owners and are not inferred from this subscription work.

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

Title: Keep subscription notices readable across themes
Target: main
Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-acceptance

Description: Replace hardcoded subscription colors that made effective-date and
tax notices unreadable in dark mode with existing semantic theme colors. Native
staff pause/resume/close/renewal and next-cycle edit/reload checks pass against the
real API/PostgreSQL at desktop/mobile sizes in both themes; notice contrast is
7.96:1 dark and 10.88:1 light. All 113 frontend tests, typecheck, lint and build
pass. Only the owned stylesheet and this evidence handoff change; joint T31 remains
an explicit separate integration gate.

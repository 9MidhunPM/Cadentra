# Thanushree Suresh: handoff

Status: SUBSCRIPTION ROLE ACCEPTANCE VERIFIED

Role: Subscription Workflows
Branch: feature/subscription-completion
Reviewed main incorporated: ff18b1fa75e72edd5f9b61ff7b2064ba7da4270d
Backend workflow/API commit: f8fa86715ad607936fbec559a198f7ed2eb9abb4
Staff UI commit: 58fbb5f6f634a0da842a2beac952675174050941
Projection privacy fix: f6acf92b6e35a49a29c9f292cc4216ffdcceecc1
Frozen policy verification: 2d61b8d51a45a2df13edb8a868950046ca887a76
Named template plan labels: c046593f7e91b9fdd58f0b2d16dbd863988fdae5
Lifecycle/availability boundary coverage: 3f759740b2196f3d8973ba5798214d85d18f3980
Actual worker/action race verification: a9817959c5af35b06b5d1eecdf3279974423334a
Theme notice contrast fix: a9b7a0c1b9f6b453395565effc1f34457c5079d6
Owner SSH integration: 18e88ff7e1b9abfb2d17c4be50b2e929267c437f
Joint browser/test-only correction: 41ef6df0521d853348803cd71471d5852b7bc313 (Sherin Saji)
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
  361 passed, 121 subtests passed in 75.56s on reviewed portal 09d4a62 plus main
  2967a8e. Subsequent main ff18b1f has exactly the same backend/frontend Git tree
  hashes and tracked application-file fingerprint as that tested combination.
  Backend tree: 20c3ce708ef888705c6adeb1aebdf26be77a6ecb.
  Includes all 124 subscription cases: 10 calendar,
  25 billing-input, 52 workflow, 27 API, four actual worker and six race cases.
  No missing-service skips. The 13 added guard cases cover future activation,
  terminal-state edits, renewal date constraints, due pause/close guards,
  requested-start availability endpoints and template-plan mismatch.
- Real template copy/edit race uses independent connections and observes an
  actual PostgreSQL lock wait; cached template rows refresh coherently.
- Policy tests cover disabled pause/close/renew for staff and an actual customer
  owner, asserting conflict/no mutation/no misleading action hint.
- Final portal-combined frontend run: all 156 tests passed across 13 files in
  4.49s after consuming Sherin Saji's test-only 41ef6df correction. It waits for
  the actual focus effect while retaining the privacy/title/navigation checks.
  The initial 155/156 run and focused pass were reported before this correction;
  neither was used to claim a green full suite.
- npm run typecheck, npm run lint, npm run build: PASS.
  The shared bundle-size advisory remains a warning, not a performance claim.
- backend/.venv/bin/ruff check backend scripts/smoke.py: PASS.
- python3 scripts/check_pack.py and git diff --check: PASS.
- Independent standards/specification/UI reviews found issues that were fixed;
  final focused reviews have no remaining blocker in the owned code.

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

## Joint T31 and live portal ownership evidence

Sherin Saji executed the actual Chromium journey: one test passed in 16.6s at
clean 41ef6df on the reviewed ff18b1f application runtime. The sanitized report
records identical clean start/end Git heads, Chromium 156.0.8078.4, desktop
1440x1000/customer mobile 390x844 and the private test-only business date
2026-11-02. Thanushree's workspace independently inspected the report, executable
assertions and screenshots; it did not read the private credential manifest.

The real UI created catalog/variant/rules, plan, template and the required
DRAFT -> QUOTATION -> CONFIRMED -> ACTIVE progression. Due billing created one
invoice and replay created none. INR 4970.16 was settled by payments 2000.00 and
2970.16, with PAID/zero balance and both payments preserved after reload. Filtered
reporting and authenticated customer invoice reload/print reconciled those values.

The customer scheduled pause for 2026-12-02, cancelled the pending pause, scheduled
close for that boundary while retaining ACTIVE, and created/reloaded a new linked
DRAFT for 2026-12-02 through exclusive 2027-01-02. The paid invoice stayed unchanged.
A second authenticated customer received 404 for subscription/invoice/print and
all four actions. The complete owner subscription-ID set, original revision,
invoice/payment counts and settled amounts stayed unchanged; safe projections and
zero browser page errors were asserted. All ten verification stages are present.

Reproducible assertion source: frontend/e2e/complete-journey.ts and
frontend/playwright.journey.config.ts. Local sanitized proof and screenshots are
under /home/midhun/Coading/Cadentra/agent4/frontend/test-results/complete-journey/
complete-journey.ts-T31-pr-5f403-nd-isolated-customer-portal-complete-journey/.
The report is T31-evidence.json; renewal, paid-invoice, reconciled-report and print
captures are separate artifacts. Do not read or publish the private seed manifest.

## Role completion and limits

T09-T13, T33-T34 and the subscription contribution to T06/T31 now have actual
service/API/worker/concurrency/browser evidence. The final independent role audit
found no remaining functional verification gap. PR #14 integrated the worker/race
slice at 209fef8a35d880133f6c011ab6357b5c7ea02502; owner-key integration preserved
the reviewed theme fix at 18e88ff. The final test-only correction and this closing
handoff follow the same reviewed, serialized owner-key integration workflow.

Actual integrated evidence: four real worker cases and six real billing/action
lock-order cases pass in the final 361-case backend run.
The worker cases create real subscriptions and invoices, retain historical PAUSED
outcomes and defer closure until backlog is drained. Race tests use three distinct
physical connections, observed PostgreSQL Lock/blocking-PID relationships and both
lock orders for edit/pause/close; historical invoice snapshots/dates remain intact
and only future cycles change. No alternate billing service is used. Each fixture
migrates and removes only its own freshly created UUID schema in the separate
integration test DB. Final standards/specification source reviews found no blocker.
The final integrated run includes all ten cases; no seeded period outcome stands
in for actual billing in these worker/race tests.

The shared T31 harness's UUID-scoped cleanup rolled back on immutable tax/discount
revision guards. Its controlled fixture database/private manifest were retained
for the database owner; no guard bypass, global truncate or database drop was
performed. Future shared runs need a safely isolated namespace coordinated by
that owner. This cleanup limitation does not invalidate the completed functional
journey. Deployment, external email delivery and all-surface performance evidence
remain with their owners; this handoff makes no such completion claim.

## Coordination and integration

The user changed the workflow after billing PR #13: Midhun P M reviews exact
heads, then each owner merges reviewed code locally and pushes main with their
own SSH key during an explicitly serialized coordinator window. Do not create
or merge PRs through gh/API. Preserve real authorship, never force-push or delete
work, and do not change global Git/SSH/account configuration.

The approved 9672e09 slice was merged with --no-ff from verified main 6cd8b74 and
pushed by Thanushree's configured author/key to main 18e88ff. A subsequent SSH
ls-remote verified the exact remote SHA; local HEAD/origin/main were clean and
0/0. Pack and whitespace checks passed. No GitHub API mutation was used.
Use command-local ssh -F /dev/null -i "$HOME/.ssh/gh-agent2" -o IdentitiesOnly=yes
with normal Git push, preserving host-key checks. No private key was read or copied.
Keep atomic active-work commits within 30 minutes, incorporate reviewed main at
least hourly, and report ready slices sooner. Preserve both earlier feature branches.

Title: Record completed subscription acceptance
Target: main
Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-completion

Description: Record the final subscription interfaces, actual PostgreSQL worker
and lock-race checks, staff desktop/mobile action QA and inspected paid-invoice/
customer-portal journey. All 361 backend tests/121 subtests and 156 frontend tests
pass; typecheck, lint, build, Ruff and pack checks pass. Only owned evidence docs
change beyond the separately owner-reviewed test-only correction. Preserve the
explicit isolated-fixture cleanup and release/performance limits above.

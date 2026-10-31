# Thanushree Suresh: handoff

Status: PURE CALENDAR IMPLEMENTED AND TESTED; PERSISTED WORKFLOWS PENDING

Role: Subscription Workflows
Branch: feature/subscription-workflows
Baseline: 766cb2664ded48afcb1012001565cbbf65c68142
Setup commit: c4ea2e4abc22e59790afd51c395249bb7b343aa8 (pushed through gh-agent2)
Preparation commit: 208adf0a0bdb2d384da15e4186e0d5e2be3afd2c
Boundary-case commit: 487cabd28a3207eb31f05bdf47225f84a6db9c11
Calendar implementation commit: bdb1cf29447ca9d7303d27e049dd61ac31ad6214
Persistent application commit: NONE

## Delivered slice
Created the subscription feature branch from the reviewed main baseline. Verified
the existing Git author configuration and authenticated the requested gh-agent2
SSH key as thanushreesuresh. The setup checkpoint was pushed successfully before
feature preparation began.

Prepared independent calendar fixtures and declarative lifecycle scenarios under
the owned subscription tests. The README maps them to acceptance IDs and explains
how to bind them to the actual services after Gate A. Lifecycle scenario execution
and persistent workflow acceptance remain NOT RUN.

The follow-up boundary slice adds coordinator-agreed exclusive quote deadlines,
requested-start plan availability, template input precedence and state-specific
PATCH cases. It records intended Gate A interfaces without creating production
stubs or changing shared files.

The coordinator subsequently authorized the pure calendar module before Gate A,
using the agreed signature and no alternate models or scaffold. Implemented
CycleSnapshot/get_cycle_bounds and executable standard-library unit tests. This
is actual calendar behavior; persistent lifecycle, API and feature UI remain
unimplemented pending the integrated foundation.

## Files changed
handoffs/thanushree-suresh.md
backend/app/modules/subscriptions/calendar.py
backend/tests/subscriptions/README.md
backend/tests/subscriptions/calendar_cases.json
backend/tests/subscriptions/check_prepared_cases.py
backend/tests/subscriptions/lifecycle.feature
backend/tests/subscriptions/test_calendar.py

## Tests actually run
- `PYTHONPATH=backend python3 -m unittest discover -s backend/tests/subscriptions -p 'test_calendar.py' -v`:
  PASS, 10 tests against the actual module; 43 golden boundary dates, six capped
  periods, invalid indices/dates/cadence, exhausted cycles, huge indices,
  date.max limits and immutable snapshots. First run was red with ModuleNotFoundError
  before the production module was written; no tests are skipped.
- `python3 scripts/check_pack.py`: PASS (planning structure, fixtures and examples only).
- `bash scripts/preflight.sh`: exit 0; Docker unavailable in this environment.
- `python3 backend/tests/subscriptions/check_prepared_cases.py`: PASS; 12 boundary
  cases (43 expected dates), 6 eligible period cases, and all four unchanged
  canonical fixtures compared with the planning reference only.
- `git diff --check`: PASS. Inline standard-library inventory/table-width check
  found 18 scenarios and 10 outlines (71 expanded cases); this is static inventory,
  not a Gherkin parser or runtime. No Gherkin steps were executed.
- `python3 -m compileall -q backend/tests/subscriptions`: PASS.
- Inline standard-library negative controls with temporary copies: the asset
  validator rejected month-end drift, duplicate IDs, a missing canonical fixture
  and a period starting at expiry. Repository fixtures were not changed.
- Independent standards and specification reviews: no remaining blocking
  findings. Corrected the shortened-period scenario to process cycle 0 before
  billing cycle 1 on its due date.
- SSH authentication with gh-agent2: GitHub identified thanushreesuresh. GitHub's
  expected no-shell exit status was 1. The setup branch push succeeded.

## Manual verification
Calendar correctness has unit evidence only. Persisted application/browser
verification is not performed; the shared foundation is not integrated.

## Implemented calendar interface

`app.modules.subscriptions.calendar` exports frozen
`CycleSnapshot(start_date: date, end_date: date, cadence: str, close_effective_on: date | None = None)`
and `get_cycle_bounds(snapshot, cycle_index: int) -> tuple[date, date] | None`.
Construct the snapshot from agreed ORM values at the integration boundary;
original subscription dates remain separate from the frozen plan snapshot.
No database, injected clock or financial computation is used by this module.

Example: start 2027-01-31, end 2027-05-01, MONTHLY, index 1 returns
(2027-02-28, 2027-03-31). Due-date filtering stays in the worker. Full persistent
APIs and sample requests will accompany the post-Gate-A service slice.

## Agreed Gate A contracts; implementation pending

Midhun P M confirmed these interfaces through user-authorized TUI coordination on
31 October 2026. They guide foundation implementation; Gate A is still pending.

- Shared exports: `app.core.auth` Actor/require_actor/require_role;
  `app.db.session` get_session/SessionFactory; `app.core.clock` get_clock;
  `app.core.money` money; `app.core.errors` DomainError. Sessions are synchronous.
- `get_cycle_bounds(snapshot, cycle_index)` takes the original start date,
  cadence, exclusive end date and optional close cap. It returns a date tuple or
  None when no eligible period remains, and raises ValueError for invalid index
  or cadence. The worker separately checks period_start against as_of.
- `get_billable_inputs(db, subscription_id, cycle_index)` is read-only and serves
  only the next unprocessed cycle. The immutable result includes IDs, revision,
  currency, terms, cycle index/bounds, effective end, pause disposition and frozen
  pricing sources. It contains exactly one BASE line with quantity 1 plus product
  lines keyed by persisted line IDs. Unit prices already include variant deltas.
  Each line carries product/variant IDs, description, quantity, Decimal price,
  stable tax identities and its source snapshot. Never add base or variant twice.
- Getter validates negative/noninteger indices before cursor comparisons with
  INVALID_CYCLE/409. Other conflicts: non-ACTIVE -> INVALID_TRANSITION; index below cursor ->
  PERIOD_ALREADY_PROCESSED; above cursor -> INVALID_CYCLE; current index beyond
  effective end -> CYCLE_OUT_OF_RANGE (all 409). Missing subscription ->
  NOT_FOUND/404. Pause remains ACTIVE and returns paused=True. Billing reuses a
  durable outcome before requesting inputs. Getter never commits or reprices.
- selected_tax_ids and plan tax IDs remain stable tax_rules UUIDs; billing resolves
  immutable tax_rule_revisions at period_start. Invoice tax records retain stable
  identity, revision reference and name/rate/amount snapshots. Tax calculations
  remain in billing. Coordinator owns the models, revisions and numbering.
- Product memberships are selected per target period_start using the shared
  Catalog.get_product_tax_ids helper; quote/start-date filtered membership lists
  must not freeze out a tax that becomes applicable later. Product prices remain
  frozen. The base-fee line retains explicitly selected stable plan tax IDs from
  plan_snapshot; rates are still period-specific in billing.
- The caller owns apply_action's transaction. Schedule/line mutations share the
  subscription row lock used by billing. Lifecycle processing defers terminal
  closure until earlier due periods have durable outcomes.
- Resume cancels a wholly unapplied pending pause by removing its interval in the
  same transaction as a redacted cancellation audit event. Never insert a
  zero-length interval. Once any PAUSED outcome exists, preserve it and resume at
  the first original boundary on/after today and at/after the next unprocessed
  cycle; no back-billing or rewriting completed outcomes.
- quotation_valid_until is an exclusive business DATE; confirm only while today
  is before it. Plan availability checks requested start_date in [from, until).
- DRAFT permits SubscriptionEdit fields; QUOTATION requires revise first;
  CONFIRMED/CLOSED reject edits; ACTIVE permits only lines for the next unprocessed
  cycle after the due-backlog guard.
- Template plan_id must match. Omitted lines copy the template; explicit lines
  override and receive full validation. Explicit [] is not a template fallback;
  null is rejected, and omission without a template is rejected. Coordinator
  updates the shared SubscriptionCreate schema to make lines optional.
- plan_snapshot schema_version=1 retains the documented pricing/cadence/policies
  and plan tax IDs. Money, dates, enums and UUIDs serialize as strings; flags
  remain booleans and schema_version/min_quantity remain integers.

## Remaining shared dependencies

- Midhun P M: integrate actual imports/ORM models, shared concrete DTOs and
  disposable PostgreSQL fixtures, and record these agreements in shared contracts.
- Sherin Saji confirmed the feature getRoutes factory and shared client/UI exports
  in frontend foundation 43ed550 are stable for domain owners. Additional new-form
  routes stay inside the subscription factory. Portal projection follows the
  safe docs/05 essentials with ownership rechecked in query/action services.

No additional schema change is requested beyond the coordinator-owned foundation.
If a missing persistent field is found, request type, nullability, default and
rationale before implementation.

## Known gaps and next dependency
Application implementation awaits the integrated, verified Gate A baseline.
There are no shared application models, dependency lockfiles or database test
harness on this main baseline. Docker is unavailable in this environment. Pure
calendar tests ran; PostgreSQL, concurrency, lifecycle, browser, deployment and
email checks have not run for this workstream.
The coordinator is now implementing the backend foundation. A temporary native
PostgreSQL runtime is planned but is not yet verified. Neither this plan nor
available feature branches establishes integrated Gate A readiness.

Latest reviewed origin/main: 766cb2664ded48afcb1012001565cbbf65c68142, fetched
through gh-agent2 at the 04:48 UTC / 10:18 IST checkpoint on 31 October 2026.
It is already an ancestor of this branch; no merge is needed at that checkpoint.

The connected GitHub API account is 9MidhunPM; SSH push authentication is the
verified thanushreesuresh account. API account identity is not inferred from SSH.
If a participant-authenticated PR session is unavailable, Midhun P M can create
the prepared PR from the comparison link below without global account switching.

## Next slice
After the integrated Gate A baseline is verified, bind the prepared cases to the
agreed services, reuse the tested calendar and implement lifecycle validation and the persisted
template -> draft -> quotation -> confirmation -> activation slice. Follow with
staff UI and policy actions. Keep commits atomic and checkpoint active work at
least every 30 minutes, as requested by the user.
While active, refresh and incorporate reviewed origin/main at least hourly and
send commit/check/dependency checkpoints to Midhun P M. Report ready slices sooner;
the coordinator serializes tested PR merges into main. Do not merge main PRs from
this workstream or bypass checks to meet the checkpoint.

## Prepared PR

Title: Implement anchored subscription calendar and prepare lifecycle acceptance cases

Target: main

Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-workflows

Description: Implement immutable scheduling inputs and original-anchor daily,
weekly, monthly and yearly periods, with exclusive expiry/closure caps and safe
exhaustion at large indices/date limits. Ten unit tests execute the actual helper.
Also prepare 71 lifecycle acceptance cases for snapshots, policies, backlog-safe
closure, customer isolation, quotation/availability boundaries, template overrides
and the edit matrix. Persistent lifecycle/API/UI behavior awaits Gate A.

Validation for PR: ten actual calendar unit tests, planning-pack check,
prepared-calendar checker, Python compilation, whitespace check and independent
reviews passed. Lifecycle scenarios have no runtime bindings;
PostgreSQL/concurrency/browser checks remain NOT RUN for this workstream.

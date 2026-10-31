# Thanushree Suresh: handoff

Status: PRE-GATE A ACCEPTANCE CASES PREPARED; APPLICATION PENDING

Role: Subscription Workflows
Branch: feature/subscription-workflows
Baseline: 766cb2664ded48afcb1012001565cbbf65c68142
Setup commit: c4ea2e4abc22e59790afd51c395249bb7b343aa8 (pushed through gh-agent2)
Preparation commit: 208adf0a0bdb2d384da15e4186e0d5e2be3afd2c
Boundary-case commit: 487cabd28a3207eb31f05bdf47225f84a6db9c11
Application commit: NONE

## Delivered slice
Created the subscription feature branch from the reviewed main baseline. Verified
the existing Git author configuration and authenticated the requested gh-agent2
SSH key as thanushreesuresh. The setup checkpoint was pushed successfully before
feature preparation began. No production module has been created.

Prepared independent calendar fixtures and declarative lifecycle scenarios under
the owned subscription tests. The README maps them to acceptance IDs and explains
how to bind them to the actual services after Gate A. Scenario execution and all
application acceptance results remain NOT RUN.

The follow-up boundary slice adds coordinator-agreed exclusive quote deadlines,
requested-start plan availability, template input precedence and state-specific
PATCH cases. It records intended Gate A interfaces without creating production
stubs or changing shared files.

## Files changed
handoffs/thanushree-suresh.md
backend/tests/subscriptions/README.md
backend/tests/subscriptions/calendar_cases.json
backend/tests/subscriptions/check_prepared_cases.py
backend/tests/subscriptions/lifecycle.feature

## Tests actually run
- `python3 scripts/check_pack.py`: PASS (planning structure, fixtures and examples only).
- `bash scripts/preflight.sh`: exit 0; Docker unavailable in this environment.
- `python3 backend/tests/subscriptions/check_prepared_cases.py`: PASS; 12 boundary
  cases (43 expected dates), 6 eligible period cases, and all four unchanged
  canonical fixtures compared with the planning reference only.
- `git diff --check`: PASS. Inline standard-library inventory/table-width check
  found 15 scenarios and 10 outlines (68 expanded cases); this is static inventory,
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
Application verification not performed; the shared foundation is not implemented.

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
- Getter conflicts: non-ACTIVE -> INVALID_TRANSITION; index below cursor ->
  PERIOD_ALREADY_PROCESSED; above cursor -> INVALID_CYCLE; current index beyond
  effective end -> CYCLE_OUT_OF_RANGE (all 409). Missing subscription ->
  NOT_FOUND/404. Pause remains ACTIVE and returns paused=True. Billing reuses a
  durable outcome before requesting inputs. Getter never commits or reprices.
- selected_tax_ids and plan tax IDs remain stable tax_rules UUIDs; billing resolves
  immutable tax_rule_revisions at period_start. Invoice tax records retain stable
  identity, revision reference and name/rate/amount snapshots. Tax calculations
  remain in billing. Coordinator owns the models, revisions and numbering.
- The caller owns apply_action's transaction. Schedule/line mutations share the
  subscription row lock used by billing. Lifecycle processing defers terminal
  closure until earlier due periods have durable outcomes.
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
  Clarify negative/noninteger getter index validation before cursor comparison;
  it must not mislabel a negative index as an already-processed period.
- Sherin Saji: provide exact route factory/client/UI exports and agree the safe
  portal projection and delegated action result for T06/T31.

No additional schema change is requested beyond the coordinator-owned foundation.
If a missing persistent field is found, request type, nullability, default and
rationale before implementation.

## Known gaps and next dependency
Application implementation awaits the integrated, verified Gate A baseline.
There are no application models, services, dependency lockfiles or test harness
on this main baseline. Docker is unavailable in this environment. No application,
PostgreSQL, concurrency, browser, deployment or email check has been performed.
The coordinator is now implementing the backend foundation. A temporary native
PostgreSQL runtime is planned but is not yet verified. Neither this plan nor
available feature branches establishes integrated Gate A readiness.

Latest reviewed origin/main: 766cb2664ded48afcb1012001565cbbf65c68142, fetched
through gh-agent2 at the 04:37 UTC / 10:07 IST checkpoint on 31 October 2026.
It is already an ancestor of this branch; no merge is needed at that checkpoint.

The connected GitHub API account is 9MidhunPM; SSH push authentication is the
verified thanushreesuresh account. API account identity is not inferred from SSH.
If a participant-authenticated PR session is unavailable, Midhun P M can create
the prepared PR from the comparison link below without global account switching.

## Next slice
After the integrated Gate A baseline is verified, bind the prepared cases to the
agreed services, implement calendar/lifecycle validation and the persisted
template -> draft -> quotation -> confirmation -> activation slice. Follow with
staff UI and policy actions. Keep commits atomic and checkpoint active work at
least every 30 minutes, as requested by the user.
While active, refresh and incorporate reviewed origin/main at least hourly and
send commit/check/dependency checkpoints to Midhun P M. Report ready slices sooner;
the coordinator serializes tested PR merges into main. Do not merge main PRs from
this workstream or bypass checks to meet the checkpoint.

## Prepared PR

Title: test(subscriptions): prepare calendar and lifecycle acceptance cases

Target: main

Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-workflows

Description: Prepare subscription calendar fixtures and lifecycle acceptance
scenarios before Gate A. Preserve the canonical cadence fixtures and cover
snapshot isolation, policy actions, backlog-safe closure and customer isolation.
Cover agreed quotation/availability boundaries, template overrides and the edit
matrix, and record agreed service interfaces and remaining foundation needs.
These are prepared test assets; application behavior is not implemented or verified.

Validation for PR: planning-pack check, prepared-calendar checker, Python
compilation, whitespace check and independent reviews passed. Lifecycle scenarios
have no runtime bindings; PostgreSQL/concurrency/browser checks remain NOT RUN.

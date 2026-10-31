# Subscription acceptance cases

Status: CALENDAR, BILLING INPUTS, LIFECYCLE, API, ACTUAL WORKER AND ACTION RACE
TESTS PASS; JOINT PAYMENT/CUSTOMER-PORTAL BROWSER JOURNEY REMAINS IN INTEGRATION.

Gate A was released on reviewed main 5b78567. Set DATABASE_URL and
TEST_DATABASE_URL to this workspace's isolated databases before database tests.

## Executable PostgreSQL tests

Run `backend/.venv/bin/python -m pytest backend/tests/subscriptions -q` from the
repository root, with DATABASE_URL and TEST_DATABASE_URL set to the same isolated
PostgreSQL `*_test` database with reviewed migrations applied. The current owned
suite contains 124 tests and 80 subtests on reviewed main 382fa2b plus this slice:
10 calendar, 25 billing-input, 52 workflow, 27 API, four worker and six race tests.
The full integrated backend run passed 314 tests and 121 subtests in 59.25s,
including all 124 owned cases, against cadentra_subscriptions_integration_test.

Workflow/API tests exercise real templates, copied defaults, quoted price and
policy snapshots, required states, exclusive deadlines, activation dates,
requested-start availability, pause/resume/close/renewal and edit permissions.
They cover ownership and safe projections, identical missing/foreign errors,
actual customer policy denials, and a two-connection template copy/edit lock race.
Due-cycle tests reject line edits, pause and close without changing records or
audits. Renewal rejects both overlapping terms and backdated expired gaps.

Some lifecycle unit tests deliberately seed durable billing outcomes to isolate
the subscription service. Separate integration tests establish actual issuance:

- `test_worker_integration.py` creates subscriptions through the real required
  states and invokes the shared lifecycle/billing/outbox worker. It verifies
  bounded downtime catch-up, historical PAUSED outcomes, deferred terminal
  closure, original monthly anchors, full-priced shortened final cycles and
  early-close preservation of confirmed unpaid debt.
- `test_billing_action_races.py` runs the real issuer against edit/pause/close in
  both lock orders. Three distinct physical connections verify actual PostgreSQL
  Lock waits and blocker PIDs. Old invoice IDs, dates and snapshots stay intact;
  accepted actions affect only the next cycle, and rejected actions do not mutate
  revisions, lines, schedules or audits.

Both integration fixtures migrate and clean up only their freshly generated UUID
schemas. They do not remove public data or other workstreams' financial fixtures.
PostgreSQL 18.6 at read committed isolation was used. Native staff-browser
evidence and remaining joint T31 payment/customer-portal checks are recorded in
handoffs/thanushree-suresh.md.

### Billing-input tests

Run `backend/.venv/bin/python -m pytest backend/tests/subscriptions/test_billable_inputs.py -q`
from the repository root. The 25 cases use the real shared models, catalog helper
and PostgreSQL transaction fixtures. They exercise frozen prices, one BASE line,
cursor/state errors, pause intervals, future product-tax membership, deep
immutability, independent JSON materialization and absence of commit/outcome writes.
They do not prove billing concurrency or lifecycle/API/browser behavior.

These tests use the shared application, models and test infrastructure. They add
no competing application, dependency or runner configuration.

## Executable calendar tests

Run `PYTHONPATH=backend python3 -m unittest discover -s backend/tests/subscriptions -p 'test_calendar.py' -v`.
The 10 unittest methods exercise the actual subscription calendar module against
43 golden boundary dates and six capped periods, invalid inputs, exhausted
cycles, huge indices, date limits and immutable snapshots. They do not use the
planning reference as the implementation under test, skip absent services, or
make database/lifecycle claims.

The coordinator explicitly authorized pure calendar implementation before Gate A
because its signature was agreed. The verified integrated foundation now supplies
the models, sessions and PostgreSQL fixtures for persisted feature work.

Run `python3 backend/tests/subscriptions/check_prepared_cases.py` from the repository
root to check the calendar fixture data against the existing planning reference,
retain the canonical cases and reject malformed or ineligible period cases. This
command does not call application services or execute the lifecycle scenarios.

## Calendar fixtures

`calendar_cases.json` contains:

- `boundary_cases`: original anchor, cadence, zero-based cycle indices and
  independently specified expected schedule dates, covering T09.
- `period_cases`: eligible cycle bounds with an exclusive subscription end and
  optional early-close cap. Every case starts before its effective end.

The actual calendar service tests consume these cases using the agreed snapshot
type and retain the canonical cases from `contracts/billing-vectors.json`. The
extra cases cover leap restoration, year rollover and truncated periods. The
planning checker is not the production implementation under test.

## Lifecycle scenarios

`lifecycle.feature` expresses API/service and integrated-worker acceptance cases
in Gherkin. The `@unbound_specification` tag labels the entire feature. There are
no step bindings or Gherkin runner: do not count its 71 expanded scenarios as
executed, skipped by an application runner, or passing. Pytest evidence is
reported independently above.

| Coverage | Acceptance |
|---|---|
| T09 | All cadences, original anchors, leap dates and exclusive period caps |
| T10 | Template edits do not mutate issued quotations |
| T11 | Required progression, invalid jumps and exclusive quotation deadlines |
| T12 | Plan policies reject disallowed actions |
| T13 | Scheduled pause/resume/close, expiry and linked renewal |
| T33 | Unprocessed due periods block changes; unpaid processed invoices do not |
| T34 | Worker backlog drains before final closure |
| T06 | Cross-customer reads/actions return 404 without mutation |
| T31 | The persisted journey survives browser reload |

Additional scenarios cover minimum product quantity, requested-start availability
boundaries, template line overrides and the lifecycle-specific edit matrix.

## Integration boundaries

The tests use the integrated backend's actor, clock, models, sessions and test
database fixtures. Worker checks call the shared worker and finalized billing
issuer. The remaining joint browser journey uses Sherin Saji's shared harness and
must exercise the actual payment and portal services. No duplicate business logic
belongs in test steps.

Exercise persisted actions and worker catch-up against disposable PostgreSQL.
For billing-versus-edit/pause/close races, use two independent connections and a
barrier, then assert durable outcomes and snapshots. A sequential simulation is
not concurrency evidence. Coordinate period/invoice assertions with Noel Biju;
the subscription feature must not issue invoices itself.

Frozen contracts in docs/05 and the named handoff define exclusive quotation
dates, start-based plan availability, template line precedence and allowed edits
by state. Agreements alone do not establish passing acceptance cases. Use actual
exports; do not introduce alternate shared types or business rules in test code.

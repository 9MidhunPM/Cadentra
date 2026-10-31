# Subscription acceptance cases

Status: CALENDAR UNIT TESTS PASS; PERSISTED LIFECYCLE TESTS NOT RUN. Gate A is pending.

These assets test Thanushree Suresh's pure calendar module and prepare the
persisted subscription acceptance cases without initializing another application.
Calendar tests execute the actual helper; lifecycle scenarios still require the
shared foundation and bindings. They add no dependency or runner configuration.

## Executable calendar tests

Run `PYTHONPATH=backend python3 -m unittest discover -s backend/tests/subscriptions -p 'test_calendar.py' -v`.
The 10 unittest methods exercise the actual subscription calendar module against
43 golden boundary dates and six capped periods, invalid inputs, exhausted
cycles, huge indices, date limits and immutable snapshots. They do not use the
planning reference as the implementation under test, skip absent services, or
make database/lifecycle claims.

The coordinator explicitly authorized pure calendar implementation before Gate A
because its signature was agreed. Persistent subscription services and feature UI
still await the integrated foundation.

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

After Gate A, parameterize the actual subscription calendar service tests with
these cases using the agreed snapshot type. Reuse the canonical cases from
`contracts/billing-vectors.json`; the extra cases cover leap restoration, year
rollover and truncated periods. Do not use `scripts/check_pack.py`'s calendar
function as the production implementation under test.

## Lifecycle scenarios

`lifecycle.feature` expresses API/service and integrated-worker acceptance cases
in Gherkin. The `@pending_gate_a` tag labels the entire feature. There are no step
bindings or Gherkin runner in this planning baseline: do not count these scenarios
as executed, skipped by an application runner, or passing.

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

## Binding the tests after Gate A

Use the integrated backend's actor, clock, models, sessions and test database
fixtures. Bind calendar assertions to `get_cycle_bounds`, lifecycle assertions to
`apply_action`/`process_lifecycle`, and permission assertions to the real API and
portal services. Keep the browser journey in the feature-owned browser tests
using Sherin Saji's harness. No duplicate business logic belongs in test steps.

Exercise persisted actions and worker catch-up against disposable PostgreSQL.
For billing-versus-edit/pause/close races, use two independent connections and a
barrier, then assert durable outcomes and snapshots. A sequential simulation is
not concurrency evidence. Coordinate period/invoice assertions with Noel Biju;
the subscription feature must not issue invoices itself.

The coordinator's agreed Gate A contracts are recorded in the named handoff,
including exclusive quotation dates, start-based plan availability, template
line precedence and allowed edits by state. These agreements do not establish
that the shared foundation is integrated or that the scenarios have passed.
Bind the cases to actual exports once Gate A is verified; do not implement
alternate shared types or business rules in step code.

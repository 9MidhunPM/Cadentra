# Noel Biju: handoff

Status: BILLING ACCEPTANCE PREPARATION READY; GATE A PENDING

Role: Billing & Payments
Branch: feature/billing-payments
Baseline: 766cb2664ded48afcb1012001565cbbf65c68142
Setup commit: ca07fe256f66147fa8baca0bd40649e6c690f19f
Prepared-test commit: 813091d7819310a5e4b23a62938e72a018e979b9
Application commit: NONE

## Delivered slice
Created the billing feature branch from the reviewed main baseline. Preserved the
existing Git author configuration and authenticated the requested gh-agent3 SSH
key as noel-ult. The setup commit was pushed successfully using that key.

Prepared nine additional pricing fixtures, an executable standard-library check
against the existing planning reference, application acceptance scenarios and
real PostgreSQL race/rollback protocols. The 15 total pricing fixtures include
the six canonical cases. These files contain no application implementation.

## Files changed
- backend/tests/billing/pricing_cases.json
- backend/tests/billing/check_prepared_cases.py
- backend/tests/billing/billing.feature
- backend/tests/billing/CONCURRENCY.md
- backend/tests/billing/README.md
- handoffs/noel-biju.md

## Tests actually run
- `python3 scripts/check_pack.py`: PASS (planning structure, six arithmetic
  fixtures, four cadence fixtures and payment/example consistency only).
- `bash scripts/preflight.sh`: exit 0; Docker unavailable in this environment.
- SSH authentication with gh-agent3: GitHub identified noel-ult. GitHub's
  expected no-shell exit status was 1. Setup commit push succeeded.
- `python3 backend/tests/billing/check_prepared_cases.py`: PASS, three
  fixture/reference checks, covering 15 arithmetic vectors, stable-key allocation
  under reordered lines, finite decimal text and fixture immutability. This does
  not import or exercise an application pricing service.
- `python3 -m py_compile backend/tests/billing/check_prepared_cases.py`: PASS.
- `git diff --check` and staged whitespace checks: PASS.
- Independent standards/specification reviews: no remaining findings after
  adding the multi-product base-fee fixture and external-mail receipt scenario.

Expected canonical totals: subtotal 4680.00, discount 468.00, tax 758.16, total
4970.16. Planned payments 2000.00 and 2970.16 leave balances 2970.16 and 0.00.
Application payment, concurrency, API, browser and external-delivery tests are
NOT RUN. PostgreSQL race protocols are prepared, not passing evidence.

## Manual verification
Workspace/SSH/branch push verified. Application verification not performed.

## Required shared changes
Coordinator confirmed the following planning agreements through TUI; Midhun P M
owns recording the shared contract/model/migration changes:

- Keep stable tax/discount UUID identities. Add immutable effective-dated rule
  revisions owning configuration/product membership, and selected revision FKs
  on invoice discount and line-tax snapshots. Shared discount uses_count remains
  on the stable parent; revisions do not reset it. Serialize edits on the parent,
  enforce nonoverlapping [effective_from, effective_until) intervals and unique
  parent/effective_from; PATCH dates begin no earlier than the next business day.
  Retain separate eligibility windows. This supports historical catch-up.
- invoice_date is actual creation business date in Asia/Kolkata; due_date adds
  subscription payment terms. Keep original period bounds and preserve stored
  invoice/due dates on replay and confirmation. Worker as_of is a cutoff, not an
  arbitrary production invoice-date override. Tests inject the shared clock.
- Subscription inputs have exactly one flattened BASE line and already-adjusted
  product unit_price, immutable bounds, product quantities and stable selected
  tax IDs. Billing resolves tax revisions and chooses discounts at period_start.
  Reuse an existing period outcome before requesting current subscription inputs;
  due-date filtering belongs to billing/worker, not an implicit getter clock.
- Foundation imports/types await the integrated Gate A baseline. Proposed shared
  imports are app.core.auth Actor/require_actor/require_role, app.db.session
  get_session/SessionFactory, app.core.clock get_clock, app.core.money money and
  app.core.errors DomainError. No competing stubs are created here.

## Known gaps and next dependency
Application implementation awaits the integrated, verified Gate A baseline.
Docker is unavailable in this shell. The coordinator is investigating a temporary
native PostgreSQL runtime, but it is not yet verified; no database tests are
claimed. No invoice/payment schemas or safe print functions are implemented yet.
The agreed future invoice-query/print services must enforce actor ownership,
omit costs/private staff notes, and escape printable HTML. Send returns a queued
outbox result; local capture or SMTP acceptance is not external delivery proof.

The GitHub CLI account is 9MidhunPM while the verified push key is noel-ult. No
account switching was performed. PR creation is delegated to the coordinator
using the prepared details below.

## Next slice
After Gate A, incorporate reviewed main, run both fixture sets against the actual
calculator, then implement atomic due-period issuance and real PostgreSQL races
before rule/payment/UI completion. Use atomic commits and checkpoint active work
at least every 30 minutes, as requested by the user. Incorporate reviewed main
at least hourly while active and coordinate integration with Midhun P M.

## Prepared PR

Title: Prepare billing pricing and concurrency acceptance coverage

The billing workstream now has nine additional decimal fixtures and executable
planning-reference checks, plus acceptance specifications for invoice/payment,
rule history, permissions, print/email and true two-connection PostgreSQL races.
This is pre-Gate A preparation; production billing and database safety remain
unimplemented. Checks and limitations are recorded above.

Target: main. [Create comparison](https://github.com/9MidhunPM/Cadentra/compare/main...feature/billing-payments?expand=1).

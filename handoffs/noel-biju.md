# Noel Biju: handoff

Status: PURE INVOICE CALCULATOR READY; INTEGRATED GATE A PENDING

Role: Billing & Payments
Branch: feature/billing-payments
Baseline: 766cb2664ded48afcb1012001565cbbf65c68142
Setup commit: ca07fe256f66147fa8baca0bd40649e6c690f19f
Prepared-test commit: 813091d7819310a5e4b23a62938e72a018e979b9
Pricing implementation commit: d380643f4b1b4d844d4bc51f66d70c8f24498532

## Delivered slice
Created the billing feature branch from the reviewed main baseline. Preserved the
existing Git author configuration and authenticated the requested gh-agent3 SSH
key as noel-ult. The setup commit was pushed successfully using that key.

Prepared nine additional pricing fixtures, an executable standard-library check
against the existing planning reference, application acceptance scenarios and
real PostgreSQL race/rollback protocols. The 15 total pricing fixtures include
the six canonical cases. The preparation commit contained no application code.

The coordinator then explicitly released the independent pure-pricing slice
before integrated Gate A, while deferring rule selection/persistence/cursor/API
work. Implemented immutable Decimal inputs/results, one preselected capped
discount, stable-key largest-remainder cent allocation, per-tax rounding and
NUMERIC(18,2) bounds. Inputs already contain the base line and variant-adjusted
unit prices. The calculator does not add either charge or select rules itself.

## Files changed
- backend/tests/billing/pricing_cases.json
- backend/tests/billing/check_prepared_cases.py
- backend/tests/billing/billing.feature
- backend/tests/billing/CONCURRENCY.md
- backend/tests/billing/README.md
- backend/tests/billing/test_pricing.py
- backend/app/modules/billing/pricing.py
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
- `PYTHONPATH=backend python3 -m unittest discover -s backend/tests/billing -p
  test_pricing.py -v`: PASS, 12 actual calculator unit tests including all 15
  vectors, immutable inputs/results, line/tax sums, stable-key allocation,
  independent caller precision/rounding, zero normalization and invalid values.
  The initial test-first run failed because the pricing module did not yet exist;
  the implementation now passes. These tests do not call the planning oracle.
- `python3 -m py_compile backend/app/modules/billing/pricing.py
  backend/tests/billing/test_pricing.py`: PASS.
- Both independent reviews found no remaining findings in the pricing slice.

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
- The independently released calculator currently uses an isolated Decimal
  context and HALF_UP quantization locally. Adopt the shared money helper after
  its reviewed foundation lands, retaining precision independence and bounds.

Pure pricing exports: frozen PricingLine(stable_line_key, quantity, unit_price,
tax_rates), SelectedDiscount(kind, value, eligible_line_keys), LineCalculation and
InvoiceCalculation. calculate_invoice(tuple[PricingLine, ...], discount=None)
returns Decimal line/invoice totals. Its adapter must retain exactly one BASE
line; subscription inputs keep product identity separately for eligibility.

## Known gaps and next dependency
Database-backed invoice and UI implementation await the integrated, verified
Gate A baseline. Docker is unavailable in this shell. The coordinator reports a
running temporary native PostgreSQL 18.6 server and passing initial-migration
tests in his clone; this billing clone has not configured its own database or run
database tests. No invoice/payment schemas or safe print functions are implemented yet.
The agreed future invoice-query/print services must enforce actor ownership,
omit costs/private staff notes, and escape printable HTML. Send returns a queued
outbox result; local capture or SMTP acceptance is not external delivery proof.

The GitHub CLI account is 9MidhunPM while the verified push key is noel-ult. No
account switching was performed. PR creation is delegated to the coordinator
using the prepared details below.

## Next slice
After Gate A, incorporate reviewed main and the shared money helper, then
implement atomic due-period issuance and real PostgreSQL races before
rule/payment/UI completion. Both fixture sets already pass against the actual
calculator. Use atomic commits and checkpoint active work
at least every 30 minutes, as requested by the user. Incorporate reviewed main
at least hourly while active and coordinate integration with Midhun P M.

## Prepared PR

Title: Calculate immutable invoice totals and prepare billing acceptance coverage

The billing workstream now calculates immutable invoice totals with Decimal,
deterministic capped discount allocation and separately rounded taxes. Twelve
actual unit tests cover 15 fixtures and precision/validation boundaries. Prepared
acceptance specifications cover invoice/payment, rule history, permissions,
print/email and true two-connection PostgreSQL races. Integrated issuance and
database safety remain unimplemented. Checks and limitations are recorded above.

Target: main. [Create comparison](https://github.com/9MidhunPM/Cadentra/compare/main...feature/billing-payments?expand=1).

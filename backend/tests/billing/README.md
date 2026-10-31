# Billing acceptance preparation

Status: PURE PRICING IMPLEMENTED; INTEGRATED GATE A PENDING. The coordinator
explicitly released the independent pricing calculator before Gate A. Its actual
unit tests run; invoice persistence, migration, API, browser and database tests
remain pending. No competing scaffold or dependencies are introduced.

## Executable now

From the repository root:

```sh
python3 scripts/check_pack.py
python3 backend/tests/billing/check_prepared_cases.py
PYTHONPATH=backend python3 -m unittest discover -s backend/tests/billing -p test_pricing.py -v
```

The second command uses only the Python standard library. It checks the six
canonical arithmetic fixtures plus nine additional hand-specified fixtures
against the existing planning reference calculator. It also verifies stable-key
allocation under reordered lines, finite decimal text and fixture immutability.
It does not import or exercise an application pricing function. Passing it is
evidence of coherent prepared fixtures only.

The third command tests the actual billing-owned calculator, including all 15
vectors, independent caller precision/rounding, immutable Decimal inputs/results,
per-tax cent rounding, stable-key allocation, invalid values and database money
bounds. It uses no planning reference calculator. Its result is financial unit
evidence, not PostgreSQL transaction or full-application evidence.
Tax and selected percentage-discount rates accept at most four fractional digits,
matching the agreed stored precision and preventing intermediate half-cent drift.

Additional cases cover a base fee with multiple products, zero totals,
half-cent tax rounding, product versus
subscription scope of the base fee, remainder ties, negative variant deltas,
invoice-level percentage rounding and empty discount eligibility.

## To execute after Gate A

[billing.feature](billing.feature) is an acceptance specification, not an
installed BDD test suite. It covers T08/T14-T17 and invoice/payment/rule/print
behavior in T18-T27. Translate its cases into the actual foundation's test runner;
do not add a separate test framework just for this file. Both JSON fixture sets
already run against the actual pure calculator, including per-line allocations;
bind the remaining scenarios to persisted services after the foundation lands.

[CONCURRENCY.md](CONCURRENCY.md) defines real PostgreSQL race and rollback
protocols, including shared T13/T34 pause/expiry coordination. Every such scenario
is NOT RUN until executed with actual services and independent connections.
Sequential duplicate calls or SQLite do not establish this evidence.

## Shared integration boundary

The agreed subscription DTO direction has exactly one flattened `BASE` line and
product lines whose `unit_price` already includes the quoted variant delta.
Billing must not add either twice. Base quantity never contributes to product
minimums. Stable tax identities are resolved to retained revisions at the service
period start; billing owns discount selection. Freeze concrete DTO types and
imports with the coordinator at Gate A before writing adapters.

Product tax identities come from Catalog.get_product_tax_ids at each period
start, retaining revision-owned membership history without reading live prices.
Base-fee tax selection uses the explicit stable plan_tax_ids frozen in the
confirmed plan snapshot; selected rates still resolve by period start.

The coordinator confirmed synchronous SQLAlchemy sessions, one financial
transaction owner, parent-locked rule revisions, stable rule IDs and discount
usage shared across revisions. Retained revision payloads include product
membership; effective intervals are nonoverlapping `[start, end)`. Revision
patches are prospective from at least the next business day. These agreements
await coordinator-owned documentation/models; no schema is supplied here.

The user selected actual issuance date in Asia/Kolkata plus payment terms for
invoice/due dates, while retaining the original service period. Tests must inject
the shared business clock. Replays and confirmation preserve stored dates.

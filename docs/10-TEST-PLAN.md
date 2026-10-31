# Test and acceptance plan

Use unit tests for pure calculations; real PostgreSQL integration tests for transactions/constraints; API tests for authorization/contracts; browser tests for actual workflows. SQLite or mocked repositories cannot establish PostgreSQL concurrency correctness. These are planned tests, not tests already implemented or passed.

## Critical test matrix

| ID | Test | Expected | Owner |
|---|---|---|---|
| T01 | Duplicate normalized signup email | Only one account; safe error | Midhun P M |
| T02 | Password boundary: length 8, missing upper/lower/special | Rejected; valid length 9 accepted | Midhun P M |
| T03 | Reset request/token expiry/reuse | Generic request response; one successful consumption; old sessions revoked | Midhun P M |
| T04 | Customer submits admin/staff payload | Privilege escalation rejected | Midhun P M |
| T05 | Staff creates staff/discount/tax/product change | Forbidden | Midhun P M + Noel Biju |
| T06 | Customer A requests B's invoice/subscription/print/actions | 404, no mutation or data disclosure | Thanushree Suresh + Sherin Saji |
| T07 | Variant +560.00 on 1000.00 product | Unit price 1560.00 | Midhun P M |
| T08 | Plan base fee plus multiple product lines | Base charged once; no double count | Noel Biju |
| T09 | All four cadences, month-end/leap-year | Original anchor preserved; fixture dates match | Thanushree Suresh |
| T10 | Template edited after quote creation | Existing quote unchanged | Thanushree Suresh |
| T11 | Expired quote or invalid lifecycle jump | 409 with useful code | Thanushree Suresh |
| T12 | Policy disables pause/early-close/renew | Backend rejects, UI not misleading | Thanushree Suresh |
| T13 | Paused cycle, resumed cycle, expiry | Explicit pause outcome; correct restart; no post-expiry charge | Thanushree Suresh + Noel Biju |
| T14 | Canonical money fixture | Total 4970.16 | Noel Biju |
| T15 | Fixed discount larger than eligible base | Capped; total never negative | Noel Biju |
| T16 | Product-scope discount and multiple taxes | Only eligible lines discounted; per-tax rounding correct | Noel Biju |
| T17 | Expired/minimum/exhausted discount | Not selected automatically | Noel Biju |
| T18 | Usage-limit=1, two concurrent eligible subscriptions | At most one discounted invoice | Noel Biju |
| T19 | Two independent DB sessions run same due cycle simultaneously | One period and one invoice | Noel Biju |
| T20 | Retry after successful billing or process crash before commit | No duplicate; uncommitted work rolls back | Noel Biju |
| T21 | Worker downtime spanning several cycles | All due eligible cycles covered; pauses not reported as gaps | Noel Biju |
| T22 | Partial 2000.00 then final 2970.16 payment | Balance 2970.16 then 0; status Paid only at settlement | Noel Biju |
| T23 | Payment same key/same payload; same key/different payload | Replay then conflict; no second record | Noel Biju |
| T24 | Two concurrent payments each exceeding shared remaining capacity | At most allowed aggregate; no negative balance | Noel Biju |
| T25 | Cancel paid/part-paid invoice | Rejected; no deletion of financial history | Noel Biju |
| T26 | Catalog/rate/customer update after invoice generation | Historical invoice unchanged | Midhun P M + Noel Biju |
| T27 | Invoice send/print | Real outbox result; authorized escaped print; external delivery explicitly tested | Noel Biju |
| T28 | Report totals against recorded payments/invoices | Reconcile; date semantics match labels | Sherin Saji |
| T29 | Fresh clone with lockfiles/migrations/seed | Reproducible startup, no developer-local dependency | Midhun P M |
| T30 | Dashboard and lists with thousands of subscriptions | Measure source's <2s page target; record actual results | Sherin Saji |
| T31 | Full browser flow and reload | Product->quote->active->invoice->payment->portal persists | Sherin Saji; all four resolve defects |
| T32 | CSRF/missing or hostile Origin on mutations | Rejected without side effects | Midhun P M |
| T33 | Active-line edit while prior cycles still due | DUE_BILLING_PENDING; no retroactive repricing | Thanushree Suresh |
| T34 | Auto-close tick after downtime | Prior eligible periods processed before terminal closure | Thanushree Suresh + Noel Biju |

## Concurrency protocol

Use two independent database connections and a synchronization barrier. Invoke actual application services with separate transactions. Wait for both completions; query counts, period keys, discount redemptions, payment sums and statuses. An in-memory loop calling the service twice sequentially does not test races. Include rollback behavior after constraint violations.

## Financial fixtures

`contracts/billing-vectors.json` contains expected decimal results, fixed-discount allocation, payment balances and cadence dates. `scripts/check_pack.py` independently validates the arithmetic fixtures. The application must add its own tests against its actual functions; pack fixture validation is not app verification.

## Performance protocol

Seed at least 5,000 subscriptions, 20,000 invoices and related payments into a disposable database. Record environment, commit, row counts, cold/warm state, route, sample size and browser/API timings. Exercise overview, subscriptions list, invoices list, customer portal and filtered drilldowns. Record p50/p95/max; inspect slow queries. API p95 below two seconds alone does not establish the brief's every-page requirement. Do not invent benchmark numbers.

## Release-blocking failures

Cross-customer disclosure, incorrect arithmetic, duplicate invoice/payment creation, inaccessible login/reset flow, broken core end-to-end demo, hard-coded production data, committed secrets, or migrations that cannot apply from clean state. Required but incomplete secondary scope is recorded honestly rather than hidden.

## Evidence file

Coordinator appends actual commands, results, test timestamps, commit and remaining failures to `handoffs/RELEASE.md`. Status remains NOT RUN until evidence exists.

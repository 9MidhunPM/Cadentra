# Billing PostgreSQL concurrency acceptance protocol

Status: CORE RACES EXECUTED; JOINT LIFECYCLE VERIFICATION PENDING.
The issuer and payment tests now execute real PostgreSQL services and independent
connections. This protocol still distinguishes executed evidence from planned
stronger lock-order, email and cross-workstream scenarios below.

## Harness and evidence

- Use an explicitly disposable PostgreSQL database with the coordinator's real
  migrations. Commit setup fixtures before starting contenders. Do not use SQLite,
  an in-memory repository or one connection wrapped by two Session objects.
- Each contender owns a synchronous Session, separate physical connection and
  transaction. Record distinct `pg_backend_pid()` values. A third fresh connection
  inspects committed state after both contenders finish; expire ORM caches.
- Use a two-party barrier at a test-only observation point immediately before
  each contender attempts its first contested row lock. The hook must not change
  lock order, service results or commit ownership. Never wait at a barrier while
  holding a lock the other contender needs. Do not coordinate with sleeps.
- Bound each barrier wait to 5 seconds, set transaction-local `lock_timeout` to
  5 seconds and `statement_timeout` to 10 seconds, and join both contenders within
  15 seconds. A timeout/deadlock or unexpected exception fails the case. On failure,
  release hooks and roll back/close both sessions before fixture cleanup.
- Exercise both lock-acquisition orders in controlled subcases: pause the first
  contender after its lock is acquired, start the second, observe its database
  lock wait with the observer connection, then release the first. Use one-way
  events; the first contender never waits for the blocked contender to acquire
  that lock. Bound observer polling by the same deadline.
- Inspect counts and values, not just HTTP success. Preserve baseline invoice,
  period, redemption, counter, payment and outbox values. Check returned IDs against
  committed IDs and record the tested commit, PostgreSQL version, isolation level,
  exact command, each outcome and final counts. Never include credentials.

## Race cases

| Case | Committed setup and competing operations | Required final state |
|---|---|---|
| T19: same due period | One ACTIVE subscription, one due cycle, no existing period; both callers run the actual billing service for that subscription/cutoff. Make the next cycle future so neither caller can legitimately create a second period. | Exactly one period with `(subscription_id, cycle_index)`, one linked invoice, one set of line/tax snapshots and one cursor advance. If a discount applies, exactly one redemption/counter increment. Both callers finish safely; the second may reuse the outcome or report no remaining due work. |
| T18: last discount use | Two different due subscriptions each have an eligible gross of 100.00, no taxes and one shared fixed 10.00 discount with `usage_limit=1`, `uses_count=0`. Run billing for one subscription per contender, contending on the stable discount parent. | Two periods/invoices; exactly one total 90.00 and one total 100.00. Exactly one redemption; counter is 1. The loser reselects without the exhausted rule and still bills normally. No negative totals or abandoned cursor. Repeat across applicable retained revisions sharing that parent to prove revisions do not reset usage. |
| T24: competing payments | One CONFIRMED invoice with total/balance 100.00 and no payments. Submit 70.00 and 60.00 with distinct request keys and valid dates. | Exactly one payment is accepted; the other gets the documented business conflict after rereading balance under lock. Final paid sum is 70.00 or 60.00, balance is 30.00 or 40.00, and invoice remains CONFIRMED. No negative balance, hidden second payment or cancelled invoice. |
| T23: concurrent payment replay | One CONFIRMED invoice for 100.00. Submit the same normalized full-payment payload with the same request key from both connections. | One payment record and one 100.00 settlement; both successful responses identify that same record. Repeat a matching request after PAID and require replay. Reuse the key with a changed amount/method/date/note and require conflict without mutation. |
| T25: payment versus cancellation | One unpaid CONFIRMED invoice for 100.00. Race a full payment against cancellation with a reason, then force each lock order separately. | Payment wins: PAID with one payment, cancellation rejected. Cancellation wins: CANCELLED with reason, zero payments, payment rejected. Never CANCELLED with a payment. Keep the original period and discount use; later billing does not reinvoice it. |

Run all cases through services that own their financial transactions. A test must
not insert its own pre-lock or outer transaction that serializes away the race.
Check stable rule-ID lock ordering with two overlapping eligible capped rules;
selection must retain the best-discount rule and stable-ID tie break without
deadlock, even if callers receive candidates in opposite input order.

## Rollback and retry cases

1. **T20, fail before commit:** use a test-only fault hook after period, invoice,
   snapshots, redemption/counter and cursor changes have flushed, immediately
   before commit. Raise an intentional exception. From the fresh observer verify
   no period/invoice/lines/taxes/redemption or outbox changes, no counter increment
   and no cursor advance. Retry through the normal service; require exactly one
   complete outcome. Invoice sequence gaps are allowed; number reuse is not.
2. Repeat the before-commit fault for payment insertion and paid-state update.
   No payment or PAID state may survive. The same request key must succeed on a
   clean retry, followed by a matching replay with no second record.
3. **Constraint recovery:** independently verify the actual migrated unique keys
   for period, invoice-period, payment-key and redemption-invoice. In a service
   recovery test, force its real insert/flush boundary to encounter an already
   committed conflicting key, without replacing database exceptions with mocks.
   Require its documented savepoint rollback/upsert or full transaction rollback
   before reload. Perform a subsequent real query and permitted write through the
   recovered transaction/session; no PostgreSQL aborted-transaction state may be
   swallowed. The existing outcome is preserved and counters remain unchanged.
4. Retry successful issuance after changing current catalog/customer values and
   adding a later rule revision. IDs, invoice dates, original totals, customer,
   prices, selected revision and calculation snapshots remain unchanged. A
   cancelled invoice remains the durable outcome, with no automatic replacement.
5. For a separately requested send, race identical send keys and retry dispatch
   after simulated SMTP acknowledgement loss. Require one deduplicated outbox
   request and no new invoice/payment. Transport delivery may repeat; outbox
   state must distinguish pending/failure from successful SMTP acceptance. These
   checks do not establish external mailbox delivery. Failed financial
   transactions must not leave an orphan outbox row.

## Catch-up and lifecycle coordination (T13, T21, T34)

Use a shared injected business clock; do not expose arbitrary public `as_of`.
Fixture: DAILY anchor 2026-10-01, exclusive end 2026-10-06, pause interval
[2026-10-02, 2026-10-04), auto-close enabled, clock/cutoff 2026-10-08.

- Run lifecycle then billing with a batch limit of 2, repeating until no backlog.
  Require five original-anchor periods: indices 0, 3, 4 INVOICED; indices 1, 2
  PAUSED. Exactly three invoices, two durable pause outcomes and cursor 5.
- After the first batch, unresolved earlier periods must remain discoverable and
  `has_more_due` must be true. Lifecycle cannot terminally close and strand them.
  Once all eligible periods have outcomes, lifecycle may close the subscription.
  No period starts on/after 2026-10-06 and a repeated tick changes no counts.
- Retry after a middle-batch rollback; the failing period remains unresolved and
  later ticks cover it. Already committed outcomes are not repeated. Surface the
  subscription failure and remaining backlog without stack traces.
- Evaluate rule validity/revision by each period start, not the catch-up date.
  Apply the coordinator's recorded issue-date policy and shared clock: newly
  created invoices on this run use 2026-10-08; seven-day terms give 2026-10-15.
  Original service dates remain separate. Retry/confirmation preserves dates.
- Add a shortened final period and scheduled early-close fixture with Thanushree
  Suresh. Require the approved full-cycle price, no post-effective-end charge,
  and no skipped history. Lifecycle/subscription tests own calendar generation;
  billing verifies the supplied immutable bounds and persisted outcomes agree.

## Acceptance record

Executed at the issuer milestone: actual same-period and capped-discount races,
payment capacity/replay/cancellation races, flushed-before-commit rollback and
retry, real uniqueness-conflict recovery, bounded paused catch-up and persisted
fair traversal across a fresh interpreter. See test_issuance.py,
test_invoice_races.py and the exact commit/checks in Noel's handoff.

Controlled winner-order/concurrent-send extensions and the joint subscription
lifecycle/worker closure test are follow-up verification, not implied by the
initial race results. Mailpit captures SMTP locally; external email delivery is
explicitly deferred by the user. A written protocol, sequential duplicate calls
or passing arithmetic fixtures cannot mark an unexecuted race case as passed.

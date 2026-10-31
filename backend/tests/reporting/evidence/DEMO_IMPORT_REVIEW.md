# Post-import reporting review proposal

Prepared by Sherin Saji against reviewed main `ef3097d`. This is a proposal, not an import or a test result. The target and importer still need coordinator confirmation. No production data, retained fixture, email configuration or worker is changed here.

## Useful demo distribution

These are soft targets for clearly fictional records. Use supported domain operations and adjust the mix when policies prevent a state; do not force lifecycle flags or overwrite immutable snapshots.

| Area | Proposed mix | What it makes visible |
| --- | --- | --- |
| Customers | About 24, including one with no records | Populated lists, useful search, customer filtering and honest empty states. |
| Catalog | Six products, a few variants, four supported billing cadences, about eight templates | Varied names/prices, quantities and plan choices without crowding selectors. Keep currency INR. |
| Subscriptions | About 60: six Draft, six Quotation, six Confirmed, 36 Active and six Closed, if legally constructible | The supported lifecycle and linked history. A few legal pauses can show scheduled/effective states; raw ACTIVE state is not the dashboard active count. |
| Invoices/payments | About 100–160 invoices if the reviewed import path supports them; include paid, unpaid Confirmed and partially paid Confirmed records | Meaningful collection states and balances. Give selected invoices two or three legitimate recorded payments to expose aggregation errors. |
| Dates | Nonempty and empty days; several genuine due dates and payment dates | Readable daily/monthly charts and overdue aging. Historical events require a reviewed fictional-history import path; otherwise show correct current-period data rather than backdating records for appearance. |

Do not fabricate SMTP acceptance, delivery or failed-email rows. Do not invoke Send/Resend. Any lifecycle operation that normally queues mail must use the reviewed demo suppression mechanism or be excluded from the import. `EMAIL_FAILED=0` is useful honest output. `BILLING_DUE` is a live work queue and may clear when the normal worker records outcomes; do not keep it artificially stuck for a screenshot.

## Bounded read-only reconciliation after the approved import

1. Record the source SHA, migration, business date/timezone, import manifest and created IDs. Preserve pre-existing data. Compare created-row deltas with the manifest; derive expected figures from accepted records, not a desired dashboard total. The earlier public smoke's 150.00 is historical and must not become a hard-coded post-import expectation.
2. Read a consistent SQL snapshot. Count dashboard active records using its actual predicate: ACTIVE, in term, not effectively closed and not currently paused. Independently sum CONFIRMED/PAID invoice totals by `invoice_date` and payments by `paid_on` over `[from,to)`. Group payments by invoice before computing positive Confirmed balances and overdue balances/counts. Never multiply invoice totals through a payment join.
3. Compare `/api/v1/reports/summary` and DAILY/MONTHLY `/api/v1/reports/revenue-series` for the same range, globally and for one populated and one empty customer. Check exact decimal strings, zero buckets, boundaries and currency. Current balances/active count remain independent of the selected revenue range. If the worker changes data between HTTP reads, record that concurrency rather than reporting a false reconciliation defect.
4. Compare CycleGuard list totals, page metadata and distinct IDs with the stored source records. OVERDUE must link to a Confirmed invoice with a positive balance and past due date. BILLING_DUE must identify a due next period without a durable outcome; paused periods have their specific explanation. EMAIL_FAILED may contain only real failed INVOICE outbox entries, without exposing recipients/payloads or implying inbox delivery. Check customer filters and source links; make no billing/resend request.
5. With separately authorized demo customer sessions, inspect own profile/subscription/invoice/print records and the corresponding staff balances. Foreign IDs must return 404 and staff reports 403. Customer selection cannot override ownership. Confirm that private cost/notes/outbox payloads stay absent; retain credentials and cookies only in private files.
6. At the approved settled checkpoint, inspect desktop/mobile Overview, exact chart data, queues, customer filters and portal details in Graphite Mint and Sage Commerce. Show actual imported figures and empty states. This visual review is separate from native timing and does not prove public latency.

The independent 5000-subscription T30 UUID fixture remains unchanged and separate from this demo distribution. Its one final timing run stays held until the coordinator supplies the final source/data freeze. A richer public demo is not a substitute for that performance gate.

Definitions: [report implementation](../../../app/modules/reporting/service.py), [CycleGuard implementation](../../../app/modules/reporting/cycleguard.py), [frozen API contract](../../../../docs/05-API-CONTRACT.md).

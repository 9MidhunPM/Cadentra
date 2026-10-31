# Domain rules: frozen proposal for consistent implementation

Everything below resolves a gap in the brief unless explicitly marked Required. These are product decisions, not organiser instructions. A change requires a coordinator-approved edit before team members implement it.

## 1. Types, currency and dates

Use INR as the demo currency and display it explicitly. The brief does not prescribe a currency. Use Decimal for all calculation; JSON amounts are strings with two fractional digits. Round monetary results using ROUND_HALF_UP. Percentages are decimal strings. Quantities are positive integers. Persist UTC timestamps but define service dates in Asia/Kolkata. Date intervals use [start, end), meaning the start is included and the end is excluded. UI must explain the final service day accordingly.

Passwords require at least nine characters, an uppercase letter, a lowercase letter and a non-whitespace special character. This implements the source's “more than eight,” not “at least eight.” Do not add a mandatory digit rule that the source does not ask for.

## 2. Price composition

The plan has a **base fee per billing cycle**. Each subscription product line adds `(agreed product sales price + selected variant delta) * quantity`. Total gross = one base-fee line + all product lines. The minimum quantity counts product quantities, not the base-fee line. This additive convention resolves an ambiguity in the brief; label it clearly so users do not enter the same charge twice.

A quoted unit price is a snapshot. Product costs are internal and excluded from customer APIs. Existing line snapshots do not change when catalog prices change. Active line/quantity edits affect the next not-yet-processed cycle only. Reject edits when historical/current cycles are due but unprocessed, then let the operator run billing and retry.

## 3. Required subscription states

`DRAFT -> QUOTATION -> CONFIRMED -> ACTIVE -> CLOSED`

DRAFT may be edited and issued as QUOTATION. QUOTATION may be revised back to DRAFT or confirmed only when today is strictly before its exclusive quotation_valid_until business date. CONFIRMED becomes ACTIVE on/after start_date, by explicit staff action or lifecycle worker. Never skip required states. CLOSED is terminal; renewal creates a new linked DRAFT instead of reopening the old record.

Pause is not a sixth lifecycle state: it is a separate schedule interval shown as an ACTIVE subscription with a “Paused” collection/service label. Invoice overdue/partial-paid labels similarly do not alter the required main invoice states.

## 4. Calendar schedule and billing periods

Bill in advance at each scheduled period start. Dates are calculated from the original start_date and cycle_index, never by repeatedly adding a month to a previously clamped date.

- DAILY: original date + index days.
- WEEKLY: original date + 7*index days.
- MONTHLY: original month + index months; use original day, clamped to the target month's last day.
- YEARLY: original year + index years; use original month/day, clamped for leap-year cases.

Example: a 31 January 2027 monthly start produces 28 February, 31 March, 30 April. A 29 February yearly anchor returns to 29 February in a leap year. Period_end = min(next scheduled boundary, end_date, close_effective_on if present). Process only if period_start <= as_of and period_start < effective_end.

Proposed no-proration policy: a final shortened service period still has a full-cycle charge. Display this before confirmation; no automatic refunds. This is a disclosed limitation, not a production-ready financial policy.

## 5. Pause, resume, expiry, close and renewal

Pause requires allow_pause. Before changing the schedule, ensure already-due cycles are processed; otherwise reject DUE_BILLING_PENDING. A pause starts at the next unprocessed scheduled boundary, so the currently billed period remains unchanged. Persist the open pause interval.

Resume closes that interval at the first original-schedule boundary on or after the request date. A cycle is paused when its start lies inside an interval [starts_on, ends_on). While paused, the worker writes PAUSED period outcomes and advances its cursor; it does not create an invoice. A billing gap therefore cannot be confused with an intentional pause. Resume does not automatically extend expiry.

Early close requires allow_early_close and, after processing already-due periods, takes effect at the next unprocessed boundary (or end_date if sooner). Store close_effective_on; transition to CLOSED when it becomes effective. It does not refund or erase previously issued invoices. Display the scheduled closure date rather than falsely saying the subscription ended immediately.

At expiry, no new service period may start. If auto_close is true, transition to CLOSED after processing any earlier due periods. Otherwise retain the existing state, show “Expired, closure pending,” and exclude it from active-service counts. Staff can close an expired subscription regardless of the early-close switch.

Renew requires allow_renew. Create a new linked DRAFT with copied plan/lines and a new reference. For an active subscription, the new start is no earlier than its current effective end; for an expired one, no earlier than today. A new expiry date is required. The new record goes through the same quotation/confirmation flow. Do not back-bill a gap between terms or create overlapping renewals silently.

## 6. Discount selection and allocation

Only admin creates/edits rules. A rule's active date window is checked against period_start, not the worker retry date. Evaluate eligibility against undiscounted eligible charges. SUBSCRIPTION scope includes the base-fee and product lines; PRODUCTS scope includes only matching product lines. min_purchase refers to that eligible gross and min_quantity to eligible product quantity. Missing minimums are zero. usage_limit is global across invoices, not per customer.

Only one rule applies per invoice. Select the eligible rule producing the largest capped monetary discount; tie-break by stable rule ID. For PERCENT, compute eligible_gross * percent / 100. For FIXED, cap the fixed value at eligible_gross. Round the invoice-level discount to cents, then allocate it among eligible lines pro rata using a largest-remainder method with stable line-key ties. No line discount can exceed its gross.

Reserve/consume one usage when the draft invoice is first created, in the same transaction. Cancellation does not restore the use under this conservative MVP policy. Keep a redemption record explaining this. A retry reads the existing invoice and does not consume again. Lock/recheck eligible capped rules in stable ID order, or use a conditional atomic counter update and retry selection when a rule becomes exhausted. Never trust a separate unlocked count query.

## 7. Taxes and totals

Apply tax to each line's gross minus its allocated discount. Support multiple additive, non-compounding tax rules per line. Round each line-tax result to cents, then sum. Rule rate/date eligibility is evaluated for the service period start and snapshotted. These are illustrative configurable taxes, not a jurisdiction compliance engine.

`subtotal = sum(line gross)`
`discount_total = sum(line discounts)`
`tax_total = sum(each line-tax amount)`
`total = subtotal - discount_total + tax_total`

Canonical demo: base fee 0.00; product 1000.00; variant +560.00; quantity 3; eligible 10% discount; illustrative 18% tax. Subtotal 4680.00; discount 468.00; taxable 4212.00; tax 758.16; invoice total **4970.16**. Payments 2000.00 then 2970.16 settle it. Fixtures live in `contracts/billing-vectors.json`.

## 8. Idempotent recurring billing

For each due subscription, lock the subscription row, recompute the next due cycle, and open one transaction. Write a uniquely keyed period `(subscription_id, cycle_index)`. For a billable period, create exactly one invoice tied to that period, snapshot prices/taxes/discounts, record any redemption, and advance next_cycle_index. For a paused period, write its PAUSED outcome and advance without an invoice. Commit together.

Retry/concurrent requests encountering an existing period return/reuse its outcome. Never catch a uniqueness exception and continue a broken PostgreSQL transaction; use appropriate transaction rollback/savepoint or an upsert pattern, then reload. Do not advance the cursor before the outcome is durable. Process catch-up in bounded batches and continue on later ticks; expose remaining backlog and failures. Read pagination/chunking must not drop unresolved periods.

## 9. Invoice transitions and payment rules

Required happy path: DRAFT -> CONFIRMED -> PAID. Add CANCELLED as the cancellation outcome, as supported by the source's cancellation operation. A draft may be cancelled; a confirmed invoice may be cancelled only if no payment exists. Require cancellation reason. Paid or partially-paid cancellation is rejected because refunds/credit notes are outside this proposal. Cancelled cycles are not automatically reinvoiced and cannot be deleted to bypass uniqueness; surface them for operator review.

Payment input includes invoice, method, positive amount, paid_on, note and client-generated idempotency request_key. Permit payment only against CONFIRMED invoices. Lock the invoice, replay matching existing request keys before checking paid status, reject a reused key with a different normalized payload, and reject amounts above remaining balance. A zero-total invoice becomes PAID upon confirmation without inventing a payment.

After partial payment, invoice remains CONFIRMED with a derived Partially paid label. Exact settlement sets PAID. Outstanding = total - sum(payments). Overdue means CONFIRMED and balance > 0 and today > due_date. Draft/cancelled invoices never count as outstanding debt.

## 10. Reporting semantics

Cash received = sum of recorded payments by paid_on in selected [from,to) range. Invoiced gross = totals of CONFIRMED or PAID invoices by invoice_date in that range; label tax-inclusive. Outstanding/overdue balances and active subscriptions are present-state metrics, labelled “as of today,” optionally customer-filtered, not historical balances fabricated from today's status. Active count = state ACTIVE, within service dates, not effectively closed and not currently paused.

No MRR/ARR or recognised-revenue claims are required in this MVP. If later added, document their exact normalization and exclusions first. CycleGuard is a deterministic query of committed records; it must not claim probabilistic loss predictions.

## 11. Authentication and email

Use hashed opaque server-side sessions in HttpOnly cookies, Secure in deployment, SameSite=Lax and a restricted path/domain. State-changing requests require an allowed Origin and CSRF protection; do not rely on hidden buttons. Login/reset endpoints are rate-limited. Reset tokens are random, hashed in storage, single-use and expire after a proposed 30 minutes; consuming one invalidates existing sessions.

Local SMTP capture is development-only evidence. Verify an actual registered-email reset link and a real invoice-send path before calling delivery complete. Outbox retries must not block HTTP requests or bill again. Never store tokens in public logs or public demo screenshots.

## 12. Additional implementation guardrails

Do not attach a new unverified signup to a staff-created customer record merely because its email matches; that would grant access to pre-existing invoices without proving email ownership. For the demo, sign up the customer first or seed a verified linked account. Any later linking requires verified ownership/admin review.

Treat tax/discount rate changes as effective-dated revisions rather than retroactive mutation of historical policy. Existing invoices remain immutable; a worker catching up an old service period uses the applicable retained rule revision. If revisioning cannot be completed, disclose the limitation instead of claiming historically accurate catch-up across edited rules.

Payment paid_on must not be in the future under the real business clock. A backdated entry is an explicit staff action recorded with its separate created_at timestamp. Notes must not contain card data or bank credentials.

## 13. Recorded Gate A clarifications

Quotation validity uses an exclusive business DATE: issue_date + positive valid_days. Availability is evaluated against requested service start on [available_from,available_until). Template plan must match; omitted lines copy it, explicit lines override and are validated, null is rejected. State-specific edit and typed snapshot contracts are in docs/05-API-CONTRACT.md.

Late billing keeps original period bounds but sets invoice_date to creation business date and due_date to invoice_date + payment_terms_days. Those dates are immutable on retries and confirmation. as_of is an internal processing cutoff, not an arbitrary public invoice-date input.

Tax/discount revisions use stable parent IDs and immutable dated payloads/membership. PATCH effective_from is at least the next business day; backdated/overlapping edits are rejected. Eligibility dates remain independent. Billing resolves service-period revisions; discount caps use the stable parent counter across all versions.

Resume edge: a wholly unapplied pending pause may be cancelled with an audit event rather than persisted as a zero-length interval. Once a PAUSED outcome exists, preserve the interval/outcome history and resume at the first unprocessed original boundary on or after today. Product tax memberships are period-specific lookups over retained revisions; quoted prices remain frozen. The base fee retains explicitly selected stable plan tax IDs, resolving their rates by service period.

# Data model: proposed shared baseline

Midhun P M owns implementation and migrations. This is a specification, not migration code. IDs are UUIDs except sequential human-readable document references. Dates are ISO dates in the chosen business timezone; timestamps are UTC. Monetary columns are NUMERIC(18,2); rates may use NUMERIC(9,4). JSON amounts are decimal strings.

## Tables

| Table | Required fields and relationships |
|---|---|
| users | id, display_name, normalized_email unique, password_hash, role ADMIN/STAFF/CUSTOMER, customer_id nullable FK, active, created_at |
| customers | id, display_name, email, company_name, billing_address JSON, created_at |
| sessions | id, token_hash unique, user_id FK, csrf_token, expires_at, revoked_at |
| password_reset_tokens | id, user_id FK, token_hash unique, expires_at, used_at |
| products | id, name, product_type text, sales_price, cost_price, notes, active |
| product_variants | id, product_id FK, attribute_name, attribute_value, price_delta, active |
| plans | id, name, base_fee, currency, cadence DAILY/WEEKLY/MONTHLY/YEARLY, min_quantity, available_from, available_until nullable, allow_pause, allow_early_close, allow_renew, auto_close |
| tax_rules | id, name, rate_percent, valid_from, valid_until nullable, active |
| product_taxes | product_id, tax_rule_id; composite unique |
| plan_taxes | plan_id, tax_rule_id; composite unique; tax applies to plan base-fee line |
| quotation_templates | id, name, plan_id FK, valid_days positive, active |
| quotation_template_lines | id, template_id FK, product_id FK, variant_id nullable FK, quantity positive |
| subscriptions | id, number unique, customer_id FK, plan_id FK, prior_subscription_id nullable FK, state, start_date, end_date exclusive, payment_terms_days, quotation_valid_until, currency, plan_snapshot JSON, next_cycle_index, close_effective_on nullable, close_reason nullable, revision, created_at |
| subscription_lines | id, subscription_id FK, product_id, variant_id nullable, description, quantity, unit_price, price_snapshot JSON, selected_tax_ids JSON |
| subscription_pauses | id, subscription_id FK, starts_on, ends_on nullable; only one open interval per subscription |
| billing_periods | id, subscription_id, cycle_index, period_start, period_end exclusive, disposition INVOICED/PAUSED, explanation, created_at |
| invoices | id, number unique, subscription_id, billing_period_id unique, customer_id, status DRAFT/CONFIRMED/PAID/CANCELLED, currency, invoice_date, due_date, customer_snapshot JSON, seller_snapshot JSON, subtotal, discount_total, tax_total, total, discount_rule_id nullable, calculation_snapshot JSON, confirmed_at, cancelled_at, cancellation_reason |
| invoice_lines | id, invoice_id FK, stable_line_key, description, product_id nullable, variant_id nullable, quantity, unit_price, gross, discount, taxable_amount, tax_total, total, source_snapshot JSON |
| invoice_line_taxes | id, invoice_line_id FK, tax_rule_id nullable, name_snapshot, rate_snapshot, amount |
| discount_rules | id, name, kind FIXED/PERCENT, value, scope SUBSCRIPTION/PRODUCTS, min_purchase, min_quantity, starts_on, ends_on nullable exclusive, usage_limit nullable, uses_count, active |
| discount_products | discount_rule_id, product_id; composite unique |
| discount_redemptions | id, discount_rule_id FK, invoice_id unique, amount, created_at |
| payments | id, invoice_id FK, method MANUAL/BANK_TRANSFER/UPI/CASH/CARD_EXTERNAL/OTHER, amount, paid_on, note, external_reference nullable, request_key, request_payload_hash, created_by, created_at |
| email_outbox | id, kind RESET/INVOICE, aggregate_id, recipient, subject, payload JSON, dedupe_key unique, status PENDING/SENDING/SENT/FAILED, attempts, last_error, next_attempt_at, created_at |
| audit_events | id, actor_user_id nullable for worker, entity_type, entity_id, action, redacted_details JSON, created_at |

Use PostgreSQL sequences/identity-backed numbering or another atomic generator for human-readable subscription/invoice references. Never use COUNT(*)+1. An invoice number may have gaps; never reuse a cancelled number.

## Constraints and indexes

- normalized_email unique at database level; normalize before storage.
- billing_periods UNIQUE(subscription_id, cycle_index); cycle_index >= 0; period_end > period_start.
- invoices UNIQUE(billing_period_id), non-null for all recurring invoices in this scope.
- payments UNIQUE(invoice_id, request_key), amount > 0.
- discount_redemptions UNIQUE(invoice_id): at most one selected rule per invoice under the proposed no-stacking policy.
- quantities positive integers; rates 0-100; prices non-negative except a variant delta may be negative if resulting unit price remains non-negative.
- start_date < end_date; min_quantity >= 1; payment_terms_days >= 0.
- users with CUSTOMER role must have customer_id; staff/admin must not obtain ownership through request payloads.
- index subscriptions(state, start_date, end_date); customers display_name/email search; invoices(status, due_date, customer_id); payments(invoice_id, paid_on); billing_periods(subscription_id, cycle_index); outbox(status, next_attempt_at).
- add an index useful for finding next billing deadlines once the precise query is implemented; verify EXPLAIN rather than adding arbitrary indexes.

## Snapshot boundaries

Quotation issuance freezes quoted unit prices until revision/reissue. Confirmation freezes the plan base fee/cadence/policy switches and line prices. Tax and discount rules are evaluated for the billed service period as documented, then copied into invoice snapshots. Customer address edits and catalog/tax edits must not rewrite an already-created invoice. Product archive is preferable to deletion when referenced.

Current subscription lines may be updated for the next unprocessed cycle, but only after old due cycles have been processed; otherwise return DUE_BILLING_PENDING. Preserve audit details of revisions. There is no retroactive invoice repricing.

## Transaction boundaries

Creating signup user + customer is atomic. Advancing a due cycle, adding the period, creating its invoice, recording a discount use and advancing next_cycle_index are one transaction. Payment idempotency lookup, remaining-balance validation, insertion and invoice paid-state update run while holding an invoice row lock. Invoice cancellation and payment entry use the same lock discipline.

Document views derive paid_amount from payments and balance from invoice.total - paid_amount; avoid storing independently drifting balance columns. Denormalized counters are allowed only where the same transaction maintains them.

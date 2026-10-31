# API contract: v1 baseline

This is a proposed interface agreement, not an implemented or generated OpenAPI file. Midhun P M scaffolds shared types; each feature owner implements matching endpoints. At Gate A the coordinator freezes names. Export implemented FastAPI OpenAPI into `contracts/openapi.json` after integration and compare it with this document. Do not put an unimplemented specification behind a success response.

## Conventions

Prefix `/api/v1`. IDs are UUID strings. Enums are uppercase. Dates YYYY-MM-DD; timestamps RFC3339 UTC. Money/rates are decimal strings, never JSON floating-point values. Server computes all totals and ignores/rejects client-supplied authoritative totals. List responses: `{ "items": [...], "total": 123, "page": 1, "page_size": 25 }`; page_size max 100. Query filters use explicit snake_case names. Default list order is created_at descending with ID as a stable tie-breaker.

Successful single resource: `{ "data": {...} }`. Error: `{ "error": { "code": "INVALID_TRANSITION", "message": "...", "fields": {}, "request_id": "..." } }`. Use 401 unauthenticated, 403 disallowed role, 404 absent OR another customer's protected record, 409 business conflict, 422 validation. Do not leak stack traces.

Cookie session authentication, same-origin API proxy, `X-CSRF-Token` for authenticated mutations. Sign-in and signup verify allowed Origin and apply rate limits. API GETs do not mutate billing state. Every POST/PATCH uses server-side role and ownership checks.

## Common request schemas

Fields marked ? are optional; null must be allowed explicitly in implemented schemas. No arbitrary extra fields on financial writes.

```text
Signup: {name, email, password}
Login: {email, password}
ResetRequest: {email}
ResetConfirm: {token, new_password}
CreateStaff: {name, email, temporary_password}
CustomerWrite: {display_name, email, company_name?, billing_address?}
ProductWrite: {name, product_type, sales_price, cost_price, notes?, active?}
VariantWrite: {attribute_name, attribute_value, price_delta, active?}
PlanWrite: {name, base_fee, currency, cadence, min_quantity, available_from,
  available_until?, allow_pause, allow_early_close, allow_renew, auto_close, tax_rule_ids?}
TaxWrite: {name, rate_percent, valid_from, valid_until?, product_ids?, active?}
TemplateLine: {product_id, variant_id?, quantity}
TemplateWrite: {name, plan_id, valid_days, lines: TemplateLine[]}
SubscriptionCreate: {customer_id, plan_id, template_id?, start_date, end_date,
  payment_terms_days, lines?: TemplateLine[]}
SubscriptionEdit: {start_date?, end_date?, payment_terms_days?, lines?: TemplateLine[]}
QuoteIssue: {valid_days}
LifecycleAction: {reason?}
Renew: {start_date, end_date, payment_terms_days?}
DiscountWrite: {name, kind, value, scope, product_ids?, min_purchase?, min_quantity?,
  starts_on, ends_on?, usage_limit?, active?}
PaymentWrite: {method, amount, paid_on, note, external_reference?, request_key}
CancelInvoice: {reason}
SendInvoice: {request_key}
```

For CreateStaff, require a compliant temporary password and mark must-change-on-first-login if implemented; do not email plaintext passwords. A secure invitation flow may replace this only after a contract decision. Staff credentials used for demo must be generated locally and kept out of repository files.

## Endpoints and owners

A=admin, S=staff, C=customer-own-record. Role checks are cumulative only where listed.

| Method / path | Access | Owner | Request / result |
|---|---|---|---|
| GET /health | public, no secrets | Midhun P M | readiness status only |
| POST /auth/signup | public | Midhun P M | Signup; creates customer user, 201 |
| POST /auth/login | public | Midhun P M | Login; sets session cookie, actor + csrf token |
| GET /auth/session | authenticated | Midhun P M | actor id/name/role/customer_id + csrf token |
| POST /auth/logout | authenticated | Midhun P M | invalidates session |
| POST /auth/password-reset/request | public | Midhun P M | ResetRequest; generic accepted response |
| POST /auth/password-reset/confirm | public | Midhun P M | ResetConfirm; single-use reset |
| POST /staff | A | Midhun P M | CreateStaff |
| GET /customers | A,S | Midhun P M | paginated Customer, q filter |
| POST /customers | A,S | Midhun P M | CustomerWrite; no automatic login account |
| GET /customers/{id} | A,S | Midhun P M | Customer |
| PATCH /customers/{id} | A,S | Midhun P M | CustomerWrite subset |
| GET /products | A,S | Midhun P M | paginated product list |
| POST /products | A | Midhun P M | ProductWrite |
| GET /products/{id} | A,S | Midhun P M | product + variants |
| PATCH /products/{id} | A | Midhun P M | ProductWrite subset; archive, not destructive delete |
| POST /products/{id}/variants | A | Midhun P M | VariantWrite |
| PATCH /products/{id}/variants/{variant_id} | A | Midhun P M | VariantWrite subset |
| GET /plans | A,S | Midhun P M | paginated Plan |
| POST /plans | A | Midhun P M | PlanWrite |
| GET /plans/{id} | A,S | Midhun P M | Plan detail |
| PATCH /plans/{id} | A | Midhun P M | PlanWrite subset; existing snapshots unchanged |
| GET /quotation-templates | A,S | Thanushree Suresh | paginated templates |
| POST /quotation-templates | A,S | Thanushree Suresh | TemplateWrite |
| PATCH /quotation-templates/{id} | A,S | Thanushree Suresh | TemplateWrite subset |
| GET /subscriptions | A,S | Thanushree Suresh | customer_id, state, q filters |
| POST /subscriptions | A,S | Thanushree Suresh | SubscriptionCreate -> Draft |
| GET /subscriptions/{id} | A,S | Thanushree Suresh | SubscriptionDetail |
| PATCH /subscriptions/{id} | A,S | Thanushree Suresh | allowed fields and next-cycle line changes only |
| POST /subscriptions/{id}/issue-quotation | A,S | Thanushree Suresh | QuoteIssue -> Quotation |
| POST /subscriptions/{id}/revise | A,S | Thanushree Suresh | Quotation -> Draft |
| POST /subscriptions/{id}/confirm | A,S | Thanushree Suresh | Quotation -> Confirmed |
| POST /subscriptions/{id}/activate | A,S | Thanushree Suresh | Confirmed -> Active when eligible |
| POST /subscriptions/{id}/pause | A,S | Thanushree Suresh | scheduled pause |
| POST /subscriptions/{id}/resume | A,S | Thanushree Suresh | scheduled resume |
| POST /subscriptions/{id}/close | A,S | Thanushree Suresh | schedule early close or close expired term |
| POST /subscriptions/{id}/renew | A,S | Thanushree Suresh | Renew -> linked Draft |
| GET /tax-rules | A,S | Noel Biju | paginated rules |
| POST /tax-rules | A | Noel Biju | TaxWrite |
| PATCH /tax-rules/{id} | A | Noel Biju | safe rule revision; no historical invoice changes |
| GET /discount-rules | A,S | Noel Biju | paginated rules |
| POST /discount-rules | A | Noel Biju | DiscountWrite |
| PATCH /discount-rules/{id} | A | Noel Biju | safe rule revision |
| POST /billing/run-due | A,S | Noel Biju | no arbitrary production as_of; bounded run result |
| GET /invoices | A,S | Noel Biju | customer_id, status, overdue, from, to filters |
| GET /invoices/{id} | A,S | Noel Biju | InvoiceDetail including explanation snapshot |
| POST /invoices/{id}/confirm | A,S | Noel Biju | confirmed invoice |
| POST /invoices/{id}/cancel | A,S | Noel Biju | CancelInvoice |
| POST /invoices/{id}/send | A,S | Noel Biju | SendInvoice -> 202 outbox status |
| GET /invoices/{id}/print | A,S | Noel Biju | authenticated printable HTML |
| GET /invoices/{id}/payments | A,S | Noel Biju | actual invoice-linked payments |
| POST /invoices/{id}/payments | A,S | Noel Biju | PaymentWrite, 201 or matching replay |
| GET /reports/summary | A,S | Sherin Saji | from,to,customer_id; DashboardSummary |
| GET /reports/revenue-series | A,S | Sherin Saji | bounded from,to,cadence,customer_id?; actual data series |
| GET /reports/cycleguard | A,S | Sherin Saji | optional alerts with source links |
| GET /portal/me | C | Sherin Saji | own safe customer profile |
| GET /portal/subscriptions | C | Sherin Saji | own paginated subscriptions |
| GET /portal/subscriptions/{id} | C | Sherin Saji | own safe detail |
| POST /portal/subscriptions/{id}/{action} | C | Sherin Saji + Thanushree Suresh | action restricted to pause/resume/close/renew |
| GET /portal/invoices | C | Sherin Saji | own paginated invoices |
| GET /portal/invoices/{id} | C | Sherin Saji | own safe InvoiceDetail |
| GET /portal/invoices/{id}/print | C | Sherin Saji + Noel Biju | own authenticated print view |

The portal does not accept a customer_id filter or permit staff impersonation. Sherin Saji implements route ownership checks and invokes Thanushree Suresh's lifecycle service / Noel Biju's invoice-query or print service; it must not create parallel business logic. Internal service methods accept an actor context and recheck ownership/policy as needed. Customer renew creates a draft for staff confirmation; it never self-authorizes an invoice or payment.

## Resource response essentials

SubscriptionDetail contains id, number, customer_id, plan_id, state, start_date, end_date, payment_terms_days, quotation_valid_until, currency, plan_snapshot, lines, next_billing_date, paused/current pause interval, close_effective_on, allowed_actions, revision, and invoice references. allowed_actions is a UI hint, not authorization.

InvoiceDetail contains id, number, subscription_id, customer_id, status, collection_status, currency, invoice_date, due_date, period_start/end, safe customer/seller snapshots, lines, subtotal, discount_total, tax_total, total, paid_amount, balance_due, payments, email_status and calculation_snapshot. Customer views omit internal costs, private audit details and staff-only notes. Example: `contracts/examples/invoice.json`.

DashboardSummary contains as_of, range_from/to, currency, active_subscriptions, invoiced_gross_in_range, cash_received_in_range, outstanding_now, overdue_now, overdue_invoice_count and explicit metric_basis. Example: `contracts/examples/dashboard.json`.

BillingRunResult contains processed_periods, invoices_created, paused_periods, existing_periods, failed_subscription_count and has_more_due. Failures include safe IDs/reasons for staff, not stack traces. Worker repeats until backlog drains; the button is bounded and may report remaining work.

## Internal cross-module service contracts

```text
Identity.require_actor(request) -> Actor(id, role, customer_id)
Catalog.get_plan_snapshot(db, plan_id, effective_date) -> immutable pricing/policy inputs
Subscriptions.process_lifecycle(db, as_of) -> lifecycle changes
Subscriptions.apply_action(db, actor, subscription_id, action, payload) -> detail
Subscriptions.get_cycle_bounds(snapshot, cycle_index) -> (start_date, end_date)
Subscriptions.get_billable_inputs(db, subscription_id, cycle_index) -> pricing inputs
Billing.run_due(db_factory, as_of, limit) -> BillingRunResult
Billing.get_invoice_for_actor(db, actor, invoice_id) -> safe invoice detail
Billing.render_invoice_for_actor(db, actor, invoice_id) -> escaped printable HTML
Reporting.summary(db, actor, range_from, range_to, customer_id?) -> DashboardSummary
```

Use synchronous SQLAlchemy Session and the shared app.core.auth Actor. Concrete subscription calendar/DTO interfaces below are coordinator-approved for Gate A. Use one transaction owner per financial operation. Reporting does not call billing to generate data while reading a dashboard. Lifecycle expiry processing must defer final closure until earlier due periods have outcomes; do not close first and strand their invoices.

## Contract changes

The requesting team member records the requested field/endpoint, reason, compatibility and test impact in its handoff. Coordinator decides; Midhun P M adjusts shared models and migrations, Sherin Saji updates shared client types if necessary. Add fields compatibly during the hackathon. Do not rename endpoints because one generated component prefers another convention.

## Gate A concrete shared interfaces

Backend imports: app.db.base.Base; models from app.models; app.db.session.get_session and SessionFactory; app.core.auth.Actor/require_actor/require_role; app.core.clock.get_clock; app.core.money.money/money_string; app.core.errors.DomainError. get_session never commits implicitly. Auth reads use a separate session so business operations can own their transaction. Actor contains id, role and customer_id, plus name/session/CSRF context for identity responses.

Login and session: {data:{actor:{id,name,role,customer_id},csrf_token}}. Roles are uppercase; customer_id is nullable. Frontend modules export getRoutes(): RouteObject[]; identity also exports getStaffRoutes().

Subscriptions.calendar exports immutable CycleSnapshot(start_date,end_date,cadence,close_effective_on=None) and get_cycle_bounds(snapshot,cycle_index) -> tuple[date,date] | None. None means beyond the effective service end; invalid indices/cadences raise ValueError. The worker applies the as_of due cutoff.

BillableInputs is immutable and includes subscription/customer IDs, revision, currency, payment terms, period bounds, pause disposition, frozen policy/base-fee inputs and lines. Flatten the base fee into a BASE line (quantity 1); product-line unit_price already includes its variant adjustment. Each line retains a stable key, references, description, Decimal price, tax IDs and source snapshot. No getter commits, reprices from live catalog or selects taxes/discounts. Billing reuses existing period outcomes before asking for current inputs. Validate nonnegative integer cycle_index first (INVALID_CYCLE/409); missing subscription is NOT_FOUND/404, non-ACTIVE is INVALID_TRANSITION/409, earlier index is PERIOD_ALREADY_PROCESSED/409, future index is INVALID_CYCLE/409, ended current cycle is CYCLE_OUT_OF_RANGE/409.

SubscriptionCreate lines omission copies a matching template; omission without a template and explicit null are invalid. Explicit arrays override template lines and must pass minimum quantity validation; an empty array is not an omitted value. plan_id must match template.plan_id. DRAFT permits documented SubscriptionEdit fields; QUOTATION must revise first; CONFIRMED/CLOSED reject edits; ACTIVE permits only next-unprocessed-cycle lines after the backlog guard. Quotation deadlines are exclusive business dates computed as issue_date + positive valid_days. Plan availability is checked at requested start_date on [available_from,available_until).

Tax/discount PATCH requests add effective_from (at least the next business day), creating retained revisions; eligibility dates remain separate. Public rule IDs stay stable. No backdated, overlapping or destructive revision update is supported. Catch-up invoice_date is actual creation business date, due_date adds payment_terms_days, and original service periods remain unchanged; replay/confirmation preserves these dates.

Product tax membership is resolved for every service period by Catalog.get_product_tax_ids(db,product_id,period_start), independently of frozen prices; future-valid memberships are not frozen out at quotation. Base-fee lines retain the explicitly selected stable plan tax IDs from plan_snapshot, with revision/rate resolved at period_start. Cancel a wholly unapplied scheduled pause only with an audit event; once PAUSED outcomes exist retain history and resume no earlier than the next unprocessed original boundary on/after today.

Reporting revenue series: {data:{range_from,range_to,currency,cadence,buckets:[{period_start,period_end,invoiced_gross,cash_received}]}}. Supported cadence DAILY/MONTHLY, at most366-day query range, decimal-string amounts and exclusive upper dates. Default range is month-to-date. This report reads stored invoice/payment dates and amounts; it does not trigger billing.

Quotation validity days copied from templates persist as positive quotation_valid_days metadata in plan_snapshot and a safe response field. Confirmation rejects changed contractual plan terms with QUOTATION_PLAN_CHANGED; see domain rules.

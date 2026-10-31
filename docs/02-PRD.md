# Product requirements document: Cadentra

Version: proposed 1.0 | Build budget: eight hours | Users: Brightloop admin, internal staff, customers

## Product thesis

Recurring billing breaks when catalog, subscription status, invoices, payments and reporting disagree. Cadentra gives them one connected record of the billing lifecycle. A user should be able to answer “What does this customer owe, and why?” without opening a spreadsheet.

## Success criteria

The required end-to-end flow works with persisted records and correct authorization. All source requirements are traceable to tests. Financial totals reproduce stored calculation inputs. Billing repeats safely. Reported performance has measured evidence. No “completed” label is earned by an unconnected screen.

## Personas and permissions

**Admin:** manages staff, catalog, plans, tax/discount rules and all operational records.
**Staff:** handles customer records, templates, subscriptions, invoices and payment entry; reads catalog and reports. Cannot create staff or change pricing/tax/discount configuration.
**Customer:** sees only their own profile, subscriptions, invoices and payment history; can request allowed pause/resume/close/renew actions against their own subscription. The backend derives customer ownership from the authenticated session.

This is one seller organisation with many customer records. Multi-seller tenancy is outside this proposal. Admin/staff may view all Brightloop customers; customers may not.

## Functional requirements

### Accounts and onboarding [S1 p2]

Customer signup accepts name, email and password and creates the associated customer record atomically. Normalize email for uniqueness; reject duplicate accounts without leaking passwords. Require at least nine characters and uppercase/lowercase/special characters. Login creates a server-side session. Logout invalidates it. Reset request sends a single-use expiring link to the registered email; request response does not reveal whether the address exists. Only admin can provision staff. An admin account is provisioned by an explicit seed/bootstrap command, not public signup.

Acceptance: duplicate normalized email fails; an eight-character password fails; customer cannot submit role=ADMIN; reused/expired reset token fails; customer A cannot read customer B by guessing an ID.

### Products, variants and plans [S1 p3]

Admin manages product fields and variants with price deltas. Plans include an explicitly labelled per-cycle base fee, cadence, minimum total product quantity, availability interval and pause/early-close/renew/auto-close switches. Catalog cost price is internal only. A plan with zero base fee is valid when products supply all recurring charges.

Acceptance: variant choice changes the server-calculated unit price; each cadence can be created; ineligible quantities and unavailable plans are rejected. Price configuration cannot be modified by staff/customer. Existing invoices are unaffected by later catalog edits.

### Quotation templates and subscription lifecycle [S1 p3]

Templates contain a plan, line selections/quantities and validity days. Creating from a template copies data; later template changes do not mutate an existing quotation. Every subscription has a unique reference, customer, plan, start, expiry, payment terms and line totals. Show the five required states exactly. Expired quotations cannot be confirmed without revising/reissuing. Confirmation snapshots agreed prices and policy switches. Activation follows start date and does not bypass confirmation. Lifecycle actions are permission-checked and plan-dependent.

Acceptance: invalid transitions return a useful conflict; closing stops future cycles; scheduled expiry respects auto-close; permitted renewals create a linked new draft; prohibited actions are rejected on the server, even if called directly.

### Billing and taxes [S1 p3]

The worker runs due billing on real dates, catches up after downtime and records one outcome for each eligible cycle. The operator's run button uses exactly the same service. Draft invoices snapshot seller/customer details, lines, periods, amounts, discount and tax details. Confirmed invoices are immutable. Cancellation is supported under the documented no-payments policy. Sending uses an email outbox; printing uses a printable invoice route and browser print/save-to-PDF.

Acceptance: retry and concurrent runs do not duplicate; tax totals are computed server-side; an invoice can be confirmed, sent and printed; cancelled documents stay in the audit history; worker failures leave a retriable cycle rather than silently advancing.

### Discounts [S1 p4]

Only admin defines fixed/percentage rules, eligible products or whole-subscription scope, minimum purchase/quantity, date windows and global usage limits. Billing automatically evaluates them. The proposed non-stacking policy picks the eligible rule producing the greatest discount; deterministic ID order resolves ties. Rules and selection reasons are snapshotted on invoices. Capped usage is handled transactionally.

Acceptance: rule applies without manual invoice editing; expired, exhausted or ineligible rule does not apply; repeated invoice generation does not consume additional uses; concurrent customers cannot exceed a global cap.

### Payments [S1 p4]

Staff/admin record method, amount, date and note against a confirmed invoice. Support partial payments and multiple dates. No card or banking credentials are collected. Idempotency prevents a duplicated submission from recording a second payment. Remaining balance is computed from successful stored payment records.

Acceptance: full payment yields Paid; partial remains Confirmed with a separate “Partially paid” collection label; overpayments/negative amounts are rejected; the same request key and payload returns the original result.

### Reporting and portal [S1 pp1,2,4]

Dashboard shows current active subscriptions, invoiced amount, payments received, outstanding balance and overdue invoices. Distinguish invoiced amounts from cash received, and date-window metrics from present-state counts. Provide date/customer/status filters and paginated drilldowns. Customer portal offers its own subscriptions/invoices/payment records plus allowed lifecycle controls. Never expose catalog costs or other customers' financial records.

Acceptance: seeded and newly entered data reconcile with invoice/payment records; date filter labels match semantics; customer detail URLs are ownership checked; values survive reload.

## Nonfunctional requirements

Source target: every page responds in less than two seconds with thousands of subscriptions. Measure user-visible completion on a documented environment; API-only p95 is not proof that every page meets the source wording. Proposed engineering targets: typical list/report API p95 below 500 ms, paginated reads, no per-row query loops, and no synchronous bulk billing on page load. These targets are design aids, not measured claims.

Security baseline: hashed passwords and reset/session tokens; Secure/HttpOnly cookies in deployment; CSRF/origin protection; parameterized database access; payload validation; redacted logs; authenticated document routes; no committed secrets. Add audit events for lifecycle and financial mutations.

## Product choices requiring disclosure

INR is the demo currency, not specified in S1. Illustrative 18% tax is not a claim of Indian tax compliance. Price = plan base fee plus product/variant lines. Bill in advance; no proration/refunds; final partial service period charged at the disclosed full-cycle price. Pausing, discount usage and renewal semantics are defined in the domain rules and must not be reinterpreted independently.

## Scope control

CycleGuard is permitted only after required flow and security tests work. No live gateway or chatbot is needed to claim a functional manual-payment workflow. Do not remove required features merely to make the optional dashboard more attractive.

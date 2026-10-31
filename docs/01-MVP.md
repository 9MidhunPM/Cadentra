# MVP: one complete billing month

## Goal

Enable Brightloop staff to set up a product and plan, issue a quotation, activate the resulting subscription, produce the correct recurring invoice, record payment and see the same state in reporting and the customer's portal. This is an operator platform, not a consumer subscription-expense tracker.

## Slice A: first runnable end-to-end flow

Login as seeded admin; create a product and monthly plan; create a customer subscription through Draft -> Quotation -> Confirmed -> Active; generate an invoice from it; confirm it; record payment; reload the dashboard and customer portal and see persisted changes.

Slice A is an early integration milestone, **not full compliance**. Implement using the final data model so later features do not require a replacement billing engine.

## Slice B: minimum scope aligned with the entire brief

| Area | Required behaviour | Smallest honest implementation |
|---|---|---|
| Accounts | Unique email; password longer than eight characters, upper/lower/special; reset email | Email/password auth; hashed passwords; single-use reset link sent through SMTP; customer signup |
| Access | Admin, limited staff, own-data-only customers; admin creates staff | Backend role checks and ownership filters; simple customer portal |
| Catalog | Product name/type/sales price/cost/notes; price-adjusting variants | One catalog screen with nested variant editor |
| Plans | Price, daily/weekly/monthly/yearly cadence, minimum quantity, availability, lifecycle policies | One form with policy switches; no separate pricing-rule language |
| Quotations | Templates with plan/lines/validity; unique subscription number and required fields | Template picker, draft form and status actions |
| Lifecycle | Required five states; permitted pause/early close/renewal; automatic closure where configured | Explicit action buttons with server-enforced conditions |
| Billing | Auto-generation from subscription, taxes, confirm/cancel/send/print, no duplicate/skipped cycles | Standalone worker plus restricted “Run due billing” action using the same service |
| Discounts | Fixed/percent, scope, minimums, date validity, usage cap; automatic application | Rule editor; deterministic single-rule selection per invoice |
| Payments | Method/amount/date/note against invoice; paid/outstanding visibility | Manual payment recording, not a pretend live card gateway |
| Reporting | Active subscriptions, revenue/payments, overdue invoices, filters/summary | DB-backed reporting with clearly defined metric labels |
| Performance | Every page under two seconds with thousands of subscriptions | Indexed/paginated queries and measured test evidence; do not claim it without measurement |

Source: S1, pages 2-4. “Smallest implementation” is proposed design, not a reduced official rubric.

## Slice C: optional differentiator

**CycleGuard** identifies overdue balances, due billing periods without an outcome, and failed email deliveries. Every item links to an actual record and explains the rule that flagged it. “Explain this invoice” shows the stored quantity, variant delta, selected discount, tax and total. Do not claim probabilistic AI forecasting or live bank reconciliation.

## Explicit exclusions from the eight-hour proposal

No live payment gateway, stored card details, bank imports, tax-jurisdiction engine, multi-currency conversion, revenue-recognition accounting, event bus, Kubernetes, multi-tenant SaaS provisioning, customer usage metering or AI chatbot. S1 does not expressly request these. Mid-cycle proration and automatic refunds are not included; disclose the selected full-cycle policy.

## Things not to quietly cut

Password-reset delivery, customer isolation, quotation templates, required cadences, variant pricing, tax/discount logic and the customer portal are still source requirements. A local mail capture proves composition and SMTP submission, not external delivery. If a required item is unfinished, mark it as a gap in the requirement matrix and demo notes.

## Release acceptance

A fresh clone can start against PostgreSQL with documented commands; actual application tests pass; the demonstration flow works after a browser reload; no cross-customer data is exposed; two concurrent billing runs cannot double-invoice; real email delivery is verified or plainly listed as incomplete; the working commit is integrated according to approved event publishing rules.

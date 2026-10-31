# Functional demo and seed plan

Aim for approximately five minutes, within the organiser email's stated maximum of 5 to 6 minutes. This is a proposed script, not a claim that these features already exist. Demonstrate only working functionality and disclose unimplemented scope.

## Seed plan

Use a seed command that can run repeatedly without duplicates, gated to a demo/test environment. Create admin, staff and two customer personas. Generate their passwords locally; do not commit fixed production credentials. Use visibly fictional business data.

Seed: Brightloop business identity; a 1000.00 product; Odoo-brand variant +560.00; monthly plan with 0.00 base fee and min_quantity 3; illustrative 18% non-compounding tax; eligible 10% subscription discount; template with three seats; additional paid, overdue, paused and renewal-eligible records. Seed relative to the demo's as-of date, or clearly mark a non-production frozen demo clock. Production requests cannot advance or replace the clock.

## Five-minute story

| Time | Screen/action | Point to prove |
|---|---|---|
| 0:00-0:25 | Overview with actual seeded records | One connected view of subscriptions, money received and overdue balances |
| 0:25-1:05 | Product, variant and plan | Price delta, cadence and policy controls are real |
| 1:05-1:55 | Template -> quotation -> confirmation -> activation | Required states, customer and line snapshots |
| 1:55-2:45 | Run due billing; open invoice; run again | Correct total 4970.16 and no duplicate on retry |
| 2:45-3:25 | Confirm invoice; record 2000.00 then 2970.16 | Partial balance then Paid, linked payment history |
| 3:25-4:05 | Send/print; customer login in separate browser context | Actual email status and own-data-only invoice view |
| 4:05-4:35 | Dashboard refresh | Cash/outstanding metrics update from recorded transactions |
| 4:35-5:00 | Optional CycleGuard or required lifecycle action | Explain a real alert, or show permitted pause/renew with effective date |

If CycleGuard is unfinished, use the time for a working required action. Do not click a button that only displays an optimistic toast. A second browser profile/context avoids a fake frontend role toggle.

## Suggested spoken opening

“Cadentra brings Brightloop's products, subscription lifecycle, invoices and payments into one connected system. We will follow a customer from quotation to a paid invoice and show the same record from the customer's portal.”

## Suggested honest closing

“The demonstrated workflow uses persisted records and server-side permissions. Our README identifies the remaining limitations and the tested commit. Payments in this version are manually recorded, not charged through a live gateway.”

## Before recording

Use a clean known dataset, test credentials privately, confirm the video contains no secrets, check readable zoom and audio, and rehearse the flow against the final commit. Confirm the video link works in a signed-out browser. A local SMTP capture or draft email is not evidence of delivery to a registered external inbox.

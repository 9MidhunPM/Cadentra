# Requirement traceability and honest completion

Source references are defined in docs/00-SOURCES.md. All initial statuses are unverified: a planning document does not implement a feature. Owners update through the coordinator after integration evidence exists. Build priority does not change official scope.

| ID | Source | Requirement | Owner | Evidence/test | Current status |
|---|---|---|---|---|---|
| R01 | S1 p2 | Unique email, compliant password, signup/login | Midhun P M | T01,T02,T04 | NOT IMPLEMENTED / NOT VERIFIED |
| R02 | S1 p2 | Password-reset link to registered email | Midhun P M | T03; external delivery check | NOT IMPLEMENTED / NOT VERIFIED |
| R03 | S1 p2 | Admin/staff/customer permissions; admin-only staff creation | Midhun P M + Sherin Saji | T04,T05,T06,T32 | NOT IMPLEMENTED / NOT VERIFIED |
| R04 | S1 p3 | Products: name/type/sales price/cost/notes | Midhun P M | Catalog API/browser checks | NOT IMPLEMENTED / NOT VERIFIED |
| R05 | S1 p3 | Variants with additive price adjustment | Midhun P M | T07,T26 | NOT IMPLEMENTED / NOT VERIFIED |
| R06 | S1 p3 | Plan price, daily/weekly/monthly/yearly cadence | Midhun P M + Thanushree Suresh | T08,T09 | NOT IMPLEMENTED / NOT VERIFIED |
| R07 | S1 p3 | Minimum quantity and availability dates | Midhun P M + Thanushree Suresh | Boundary API tests | NOT IMPLEMENTED / NOT VERIFIED |
| R08 | S1 p3 | Plan-controlled auto-close, early-close, pause and renewal | Thanushree Suresh | T12,T13,T34 | NOT IMPLEMENTED / NOT VERIFIED |
| R09 | S1 p3 | Quotation templates: plan, product lines, validity | Thanushree Suresh | T10,T11 | NOT IMPLEMENTED / NOT VERIFIED |
| R10 | S1 p3 | Unique subscription number, customer, plan, dates, terms, lines | Thanushree Suresh | Subscription create/detail test | NOT IMPLEMENTED / NOT VERIFIED |
| R11 | S1 p3 | Draft -> Quotation -> Confirmed -> Active -> Closed | Thanushree Suresh | T11,T31 | NOT IMPLEMENTED / NOT VERIFIED |
| R12 | S1 p3 | Automatic invoices with customer/lines/taxes/totals | Noel Biju | T14,T19,T20,T21 | NOT IMPLEMENTED / NOT VERIFIED |
| R13 | S1 p3 | Admin tax rules and automatic calculations | Noel Biju | T05,T14,T16 | NOT IMPLEMENTED / NOT VERIFIED |
| R14 | S1 p3 | Invoice confirm/cancel/send/print; Draft/Confirmed/Paid | Noel Biju | T22,T25,T27 | NOT IMPLEMENTED / NOT VERIFIED |
| R15 | S1 p3 | No duplicate or skipped billing | Noel Biju | T19,T20,T21,T34 | NOT IMPLEMENTED / NOT VERIFIED |
| R16 | S1 p4 | Admin-only fixed/percentage discount rules | Noel Biju | T05,T15,T16 | NOT IMPLEMENTED / NOT VERIFIED |
| R17 | S1 p4 | Discount minimums, date windows, usage caps, product/subscription scope | Noel Biju | T17,T18 | NOT IMPLEMENTED / NOT VERIFIED |
| R18 | S1 p4 | Automatic next-invoice discounts and expiry/exhaustion | Noel Biju | T17,T18,T20 | NOT IMPLEMENTED / NOT VERIFIED |
| R19 | S1 p4 | Invoice-linked payment method/amount/date/note | Noel Biju | T22,T23,T24 | NOT IMPLEMENTED / NOT VERIFIED |
| R20 | S1 p4 | Paid/outstanding/overdue visibility | Noel Biju + Sherin Saji | T22,T28 | NOT IMPLEMENTED / NOT VERIFIED |
| R21 | S1 pp1,2 | Customer portal for own subscription/invoice management | Sherin Saji + Thanushree Suresh | T06,T31 | NOT IMPLEMENTED / NOT VERIFIED |
| R22 | S1 p4 | Active subscriptions, revenue/payments, overdue, filters/summary | Sherin Saji | T28 | NOT IMPLEMENTED / NOT VERIFIED |
| R23 | S1 p4 | Every page under two seconds with thousands of subscriptions | Sherin Saji | T30 | NOT IMPLEMENTED / NOT VERIFIED |
| E01 | S2 | Submit repository before 10:00 AM; obey portal timeline | Midhun P M | Portal receipt, NOT DONE | NOT IMPLEMENTED / NOT VERIFIED |
| E02 | S2/S3 | Individual contributions/hourly pushes; current evaluated code in one branch/main | Midhun P M | Publishing clarification + commit history | NOT IMPLEMENTED / NOT VERIFIED |
| E03 | S2/S3 | Evaluator/mentor collaborator; selected statement | Midhun P M | Portal and repository verification | NOT IMPLEMENTED / NOT VERIFIED |
| E04 | S2 | Accessible functional demo video, maximum stated as 5 to 6 minutes | Midhun P M | Signed-out access check | NOT IMPLEMENTED / NOT VERIFIED |

## Optional enhancements, not compliance substitutes

CycleGuard; invoice explanation panel; extended reporting; additional UI polish. Mark each separately. Do not claim an overdue-invoice list by itself is a unique predictive revenue model.

## Source gaps

No naming policy, exact feature weights, organiser approval of assistant use or unequivocal permission for remote feature branches was established. The eight-hour plan and engineering policies are ours, not official requirements.

# Requirement traceability and honest completion

Source references are defined in docs/00-SOURCES.md. Statuses below distinguish integrated local evidence from remaining acceptance checks. Owners update through the coordinator after integration evidence exists. Build priority does not change official scope.

| ID | Source | Requirement | Owner | Evidence/test | Current status |
|---|---|---|---|---|---|
| R01 | S1 p2 | Unique email, compliant password, signup/login | Midhun P M | T01,T02,T04 | IMPLEMENTED; PostgreSQL and real browser verified |
| R02 | S1 p2 | Password-reset link to registered email | Midhun P M | T03; external delivery check | LOCAL RESET/SMTP/INBOX VERIFIED; external delivery skipped until configured |
| R03 | S1 p2 | Admin/staff/customer permissions; admin-only staff creation | Midhun P M + Sherin Saji | T04,T05,T06,T32 | IMPLEMENTED; role/CSRF/staff and portal-read isolation verified; portal writes pending |
| R04 | S1 p3 | Products: name/type/sales price/cost/notes | Midhun P M | Catalog API/browser checks | IMPLEMENTED; API and real persistence browser verified |
| R05 | S1 p3 | Variants with additive price adjustment | Midhun P M | T07,T26 | IMPLEMENTED; exact additive-price API/browser verified |
| R06 | S1 p3 | Plan price, daily/weekly/monthly/yearly cadence | Midhun P M + Thanushree Suresh | T08,T09 | Catalog IMPLEMENTED/VERIFIED; subscription workflow PR11 pending |
| R07 | S1 p3 | Minimum quantity and availability dates | Midhun P M + Thanushree Suresh | Boundary API tests | Catalog boundaries verified; subscription enforcement PR11 pending |
| R08 | S1 p3 | Plan-controlled auto-close, early-close, pause and renewal | Thanushree Suresh | T12,T13,T34 | Ready subscription PR11 under review; joint issuer acceptance pending |
| R09 | S1 p3 | Quotation templates: plan, product lines, validity | Thanushree Suresh | T10,T11 | Ready subscription PR11 under review; integration pending |
| R10 | S1 p3 | Unique subscription number, customer, plan, dates, terms, lines | Thanushree Suresh | Subscription create/detail test | Ready subscription PR11 under review; integration pending |
| R11 | S1 p3 | Draft -> Quotation -> Confirmed -> Active -> Closed | Thanushree Suresh | T11,T31 | Ready subscription PR11 under review; full T31 pending |
| R12 | S1 p3 | Automatic invoices with customer/lines/taxes/totals | Noel Biju | T14,T19,T20,T21 | Manual invoice API verified; recurring issuer and staff UI pending |
| R13 | S1 p3 | Admin tax rules and automatic calculations | Noel Biju | T05,T14,T16 | Admin rules/calculation API verified; staff rule UI pending |
| R14 | S1 p3 | Invoice confirm/cancel/send/print; Draft/Confirmed/Paid | Noel Biju | T22,T25,T27 | API and owned portal print verified; staff UI/invoice SMTP capture pending |
| R15 | S1 p3 | No duplicate or skipped billing | Noel Biju | T19,T20,T21,T34 | Immutable inputs and period constraints integrated; recurring issuer/catch-up acceptance pending |
| R16 | S1 p4 | Admin-only fixed/percentage discount rules | Noel Biju | T05,T15,T16 | Admin rule API/pricing verified; rule UI pending |
| R17 | S1 p4 | Discount minimums, date windows, usage caps, product/subscription scope | Noel Biju | T17,T18 | Rules/pricing verified; issuer usage-cap integration pending |
| R18 | S1 p4 | Automatic next-invoice discounts and expiry/exhaustion | Noel Biju | T17,T18,T20 | Pricing rules verified; automatic issuer/expiry acceptance pending |
| R19 | S1 p4 | Invoice-linked payment method/amount/date/note | Noel Biju | T22,T23,T24 | API and real payment/cancellation races verified; staff UI/full journey pending |
| R20 | S1 p4 | Paid/outstanding/overdue visibility | Noel Biju + Sherin Saji | T22,T28 | API/report/portal read balances verified; full payment journey pending |
| R21 | S1 pp1,2 | Customer portal for own subscription/invoice management | Sherin Saji + Thanushree Suresh | T06,T31 | Owned portal reads/invoice print verified; lifecycle writes pending |
| R22 | S1 p4 | Active subscriptions, revenue/payments, overdue, filters/summary | Sherin Saji | T28 | IMPLEMENTED; PostgreSQL/HTTP plus owner live-browser evidence verified |
| R23 | S1 p4 | Every page under two seconds with thousands of subscriptions | Sherin Saji | T30 | PARTIAL:250 samples/10 views at recorded earlier runtime; every final page unverified |
| E01 | S2 | Submit repository before 10:00 AM; obey portal timeline | Midhun P M | Portal receipt, NOT DONE | NOT IMPLEMENTED / NOT VERIFIED |
| E02 | S2/S3 | Individual contributions/hourly pushes; current evaluated code in one branch/main | Midhun P M | Publishing clarification + commit history | Reviewed PRs/main and owner SSH pushes recorded; organiser clarification unverified |
| E03 | S2/S3 | Evaluator/mentor collaborator; selected statement | Midhun P M | Portal and repository verification | Repository collaborator list checked; portal/selected-statement acceptance unverified |
| E04 | S2 | Accessible functional demo video, maximum stated as 5 to 6 minutes | Midhun P M | Signed-out access check | NOT IMPLEMENTED / NOT VERIFIED |

## Optional enhancements, not compliance substitutes

CycleGuard; invoice explanation panel; extended reporting; additional UI polish. Mark each separately. Do not claim an overdue-invoice list by itself is a unique predictive revenue model.

## Source gaps

No naming policy, exact feature weights, organiser approval of assistant use or unequivocal permission for remote feature branches was established. The eight-hour plan and engineering policies are ours, not official requirements.

## Integrated evidence checkpoint

Reviewed main48c7896 (PR10):214 backend tests plus121 subtests and104 frontend tests pass; type/lint/build and independent reporting review pass. Identity/catalog browser persistence and local reset SMTP/inbox flow pass. See handoffs/RELEASE.md for exact limits; reports' historical performance artifact does not prove every final page. No public deployment, external SMTP delivery or submission receipt is claimed.

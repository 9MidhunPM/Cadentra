# T30 local reporting and portal baseline

31 October 2026. This is a sequential local benchmark of the implemented reporting/portal slice, not a production, concurrent-load or every-page result. Staff subscriptions returned501 and staff invoices still showed an explicit placeholder; neither received successful samples. The later reviewed privacy merge2120602 was not benchmarked by this run.

Runtime source: bec657aea61260d10c9897abdbfee86996c0faf7. The retained invoice-detail worker recorded a clean tree; the corrected final harness recorded a dirty tree containing test-only timing/capture fixes. Exact per-source metadata and hashes remain in the raw artifact. Substantive harness corrections are committed in6ec57bb.

Dataset: 5000 active subscriptions, 20000 each billing periods/invoices/lines/payments, two fictional customers. PostgreSQL sums reconciled to INR2000000.00 invoiced and INR1500000.00 paid, leaving INR500000.00 outstanding; half the invoices were fully paid and half partially paid. The fixture was subsequently cleaned by its exact recorded UUID graph, all eight involved table counts were verified zero, and private credential/session manifests were removed.

Environment: Intel Core Ultra7 255H, 16 logical CPUs, approximately32GiB RAM, Arch Linux7.2.11, Node26.12.1, Python3.12.13, PostgreSQL18.6 and Chromium156.0.8078.4;1497x1049 viewport. Vite development server5174, FastAPI8004 and PostgreSQL55431 ran on local loopback. No deployment or external network timing is claimed.

Each measured route has20 warm samples after one excluded warmup and five samples in new browser contexts sharing real authenticated test cookies. Server, database and OS caches stay warm. Browser timing covers navigation (including initial navigation before filter interaction), required successful API bodies, exact visible data, loaded fonts and two animation frames. Separate API samples include response bodies. Percentiles use nearest rank; fresh-context n=5 p95 equals its maximum.

Browser milliseconds (p50 / p95 / maximum):

| View | Warm (n=20) | Fresh context (n=5) |
| --- | ---: | ---: |
| overview-complete | 511.3 / 556.7 / 565.8 | 577.8 / 645.7 / 645.7 |
| overview-summary-chart | 500.8 / 566.5 / 604.5 | 528.0 / 648.8 / 648.8 |
| overview-customer-date-filter | 1224.0 / 1333.9 / 1372.4 | 1217.2 / 1305.7 / 1305.7 |
| portal-subscriptions-page-1 | 394.1 / 458.2 / 470.5 | 430.9 / 474.6 / 474.6 |
| portal-subscriptions-page-2 | 374.9 / 429.5 / 458.1 | 443.0 / 501.0 / 501.0 |
| portal-invoices-page-1 | 482.7 / 519.1 / 519.5 | 534.5 / 604.9 / 604.9 |
| portal-invoices-page-2 | 473.1 / 540.6 / 549.2 | 555.2 / 564.1 / 564.1 |
| portal-account | 332.0 / 413.0 / 432.8 | 374.9 / 419.8 / 419.8 |
| portal-subscription-drilldown | 369.0 / 409.6 / 420.6 | 419.2 / 438.5 / 438.5 |
| portal-invoice-drilldown | 389.5 / 435.6 / 469.7 | 490.0 / 505.7 / 505.7 |

The summary/chart row measures those components only; complete Overview additionally requires the actual overdue table and five rendered invoice records. The filtered route validates the selected customer, dates, exact summary/chart values and five matching overdue rows. Portal lists validate server totals2500 subscriptions/10000 invoices and25 rendered rows.

[Raw250 browser samples and independent API p50/p95/max](t30-2026-10-31.json) include successful bodies validated against persisted Decimal amounts, exact environment/commit provenance and explicit gaps. No credentials, cookies or response bodies are included. API query UUIDs refer only to disposable fictional customers.

The first run captured canceled React StrictMode requests and lost earlier route records on worker restart. Only its still-preserved successful invoice-detail measurements were retained. Corrected captures ignore transport-confirmed cancellation only, preserve dataset/run-specific artifacts across workers and reuse two private authenticated storage states instead of repeatedly hitting the login limiter. Lost/affected samples were rerun; failures remain described in the artifact. No failed or interrupted route is counted as a successful sample.

The full product-to-payment browser journey, staff owner screens and a final integrated release benchmark remain separate acceptance work. These results do not establish a universal two-second guarantee.

## Subsequent T31 browser evidence

On31October2026, the complete serial journey passed1/1 in16.6seconds using actual UI writes, cookies, HTTP and PostgreSQL, without request interception. [Exact per-milestone evidence](t31-2026-10-31.json) records clean source41ef6df at start/end, Chromium156,1440x1000 staff/desktop and390x844 customer views, and the fixed test-only2026-11-02 business clock. Application code matches reviewed mainff18b1f;41ef6df adds only test corrections and evidence metadata.

The browser created product/variant, tax/discount, plan/template and subscription, issued and confirmed quotation, activated service, generated one invoice and verified billing replay created none. Stored total4970.16 settled through payments2000.00+2970.16. Reports and the customer portal reconciled after reload; authenticated print omitted internal notes/costs/staff identity. Customer pause/cancel/close dates and linked Draft renewal persisted. Another real customer received404 for every foreign read/print/action, without revision, subscription-ID-set, invoice or payment changes. No page errors or mobile document overflow occurred.

This establishes the full local financial/customer journey, not external email delivery, production deployment or final large-data latency. Both servers stopped. Exact-UUID cleanup rolled back because immutable rule-history DELETE guards reject revision/membership removal. Guards remain enabled; the isolated history and private mode0600 manifest are retained pending the database owner's safe cleanup/new benchmark namespace decision. No trigger disabling, drop or production-data action occurred.

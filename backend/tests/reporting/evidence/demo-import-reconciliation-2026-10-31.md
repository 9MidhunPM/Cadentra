# Independent import reconciliation

The coordinator's completed disposable replay was checked once against independent SQL and in-process reporting HTTP routes. PostgreSQL enforced a repeatable-read, read-only transaction. No importer, production write, seed, worker or email operation ran from this checker.

Results: 192 subscriptions, 624 invoices, 843 payments and 648 billing outcomes; 96 stored Active subscriptions include 12 paused, so the reporting active count is84. Imported invoices comprise30 Draft,30 Cancelled,190 Confirmed and374 Paid. Gross4562091.00, cash3217491.20 and outstanding1344599.80 match the coordinator's replay output. Scoped outbound emails are zero.

Thirteen bounded checks passed: cohort identity/state/count reconciliation, global and one-customer summaries, all DAILY/MONTHLY bucket values and boundaries, and CycleGuard counts/date/page envelope/unique IDs. The global overdue balance is1250732.20 across177 invoices; billing-due and email-failure queues are empty at the anchor. These are not invented backlog or delivery failures.

The HTTP portion overrides the ADMIN dependency and supplies the same read-only session. It checks route serialization/projection against SQL; it does not prove production authentication, networking, portal isolation or latency. The coordinator separately reported a successful production import with matching cohort totals and preserved pre-existing record hashes. This artifact itself is the disposable-database result.

Raw sanitized evidence: [demo-import-reconciliation-2026-10-31.json](demo-import-reconciliation-2026-10-31.json). Helper: [demo_import_reconcile.py](../demo_import_reconcile.py). It accepts only the privately supplied new local import-test database and rejects both retained T31 and T30 database names. Credential values, recipients and tokens are not emitted. Its API invocation was followed only by source formatting/lint; the full performance benchmark remains paused.

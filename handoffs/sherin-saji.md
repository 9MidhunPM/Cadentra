# Sherin Saji: handoff

Status: REPORTING AND PORTAL READ SLICE IMPLEMENTED; OWNER DELEGATION AND FULL JOURNEY IN PROGRESS

Role: Experience & Reporting
Branch: feature/reporting-portal
Reviewed main: 9136adf (Gate A, subscription billing inputs, financial invoice/rule/payment APIs)
Reporting/portal backend: 2f33f9a
Reporting/portal frontend: 9edb851
Real browser harness: fcdfb7c
Delegated invoice detail/print: 53fd86b
Large-data measurement harness: 5bbdfd7
Latest reviewed-main merge: 0f97181
Previous foundation PR 2 and interface-experience PR 5 are integrated.
Setup verification commit: c4194af

## Delivered behavior

The user approved Graphite Mint as the primary/default dark theme and Sage Commerce as light mode. The references and visual/motion contract are in frontend/design/. The saved theme applies before first paint; browser theme-color now follows it. Shared navigation provides role-filtered Ctrl/Cmd K search, spring mobile navigation, tactile controls, safe route recovery, destination focus and reduced-motion support.

Reports read committed PostgreSQL data with Decimal totals serialized as strings. Summary uses one SQL statement for a consistent snapshot. Active subscriptions, outstanding and overdue are current-state metrics; invoice gross and actual payments use independent [from,to) date filters. Payment aggregation avoids invoice fanout. Revenue series supplies zero-filled DAILY or calendar MONTHLY buckets, clipped to the selected range and limited to 366 days. Midhun P M approved optional staff/admin customer_id on both summary and series on 31 October; only the coordinator edits the frozen API contract.

Overview now fetches real summary/series/overdue invoices, supports applied date/customer filters, exact accessible chart data, refresh and the owner's run-due endpoint. Displayed financial values remain server decimal strings. Numeric conversion is limited to approximate chart coordinates/axis labels. The mobile chart measures its container so labels retain readable size. Errors in independent resources remain visible.

Portal reads derive ownership from the authenticated CUSTOMER actor. Profile, paginated subscriptions/invoices and subscription detail are implemented. Foreign subscription detail returns 404; customer_id overrides are rejected. Invoice list balances come from grouped recorded payments, with separate collection_status and overdue values. Customer projections omit internal costs, audit details and staff notes. Pagination rejects offsets exceeding PostgreSQL bigint limits.

Portal frontend provides account, own subscription/invoice lists, subscription detail and stored invoice detail/print. Invoice detail and escaped HTML printing delegate to Noel Biju's services, with private/no-store responses and matching print security headers. Actions are displayed only when returned in allowed_actions; the UI does not infer plan policy. Lifecycle delegation to Thanushree Suresh remains pending; renewal will create a draft for staff review.

## Checks actually run

31 October 2026:

- Full backend at 0f97181's predecessor bb31d5e / reviewed main8c13b42: **159 tests and 121 subtests pass**, real PostgreSQL at 127.0.0.1:55431, cadentra_experience_test. Each ordinary test rolls back its outer transaction. This includes 17 reporting service, 19 report HTTP and 24 portal cases. Billing PR7 landed afterward and requires the next integrated rerun.
- Reporting/backend Ruff: pass. Source fixtures exercise real login, cookie/session auth, roles, range/cadence validation, Decimal reconciliation, owner isolation, safe projections and PostgreSQL pagination bounds.
- Frontend full lint/test/build after invoice DTO alignment and the keyboard regression: **84 tests pass**, typecheck/build pass. Customer-search Enter cannot submit filters while loading or empty. Invoice lines display stored discounts/taxes/totals and safe address fields.
- Fixture browser suite: **24 desktop/mobile cases pass, two platform-specific skips**. This suite explicitly mocks session/business reads and proves shell/keyboard/theme/reduced-motion behavior, not database correctness.
- Separate live browser suite after invoice integration: **six desktop/mobile cases pass, no skips**, real HTTP/cookies/PostgreSQL, no route interception, zero page errors. It verifies totals, filters, reload persistence, own lists/profile, foreign-subscription404, customer/report403 and own/foreign invoice detail/print200/404.
- Delegated portal PostgreSQL tests: **37 pass, one privacy regression fails**. The failing test proves upstream billing forwards nested staff_notes/internal_cost fields inside imported address JSON. Noel and the coordinator have the exact regression; do not bypass it or claim privacy completion until the owner fix is integrated. Other cases verify foreign404, staff403, anonymous401, forbidden query422, escaped print, headers and read-only SQL.
- Final live screenshots inspected at 1497x1049 desktop and 390px mobile in both approved themes. The responsive chart is readable and the actual overdue table now renders via billing PR7. Artifacts remain local under /tmp/cadentra-agent4-live-final-evidence/.
- Frontend production build about 471 kB minified /148 kB gzip plus a separate95 kB Motion feature chunk; these are sizes, not page timings. No unmeasured <2s assertion.

## Runtime and reproducible evidence

Python3.12 backend environment is installed from the coordinator-owned frozen lock. Use assigned databases only:

- DATABASE_URL=postgresql+psycopg://cadentra@127.0.0.1:55431/cadentra_experience
- TEST_DATABASE_URL=postgresql+psycopg://cadentra@127.0.0.1:55431/cadentra_experience_test

Run backend checks from backend/ with APP_ENV=test and .venv/bin/pytest -q; .venv/bin/ruff check app/modules/reporting tests/reporting. Restricted-shell loopback is isolated, so native PostgreSQL/browser processes need the authorized host network execution context. No migration/reset/drop was performed in this role.

Frontend commands from frontend/: npm run lint; npm test; npm run build. Vite binds5174 and proxies unchanged /api to API_PORT (default8004). PLAYWRIGHT_BROWSERS_PATH=/tmp/cadentra-agent4-browsers selects the installed pinned Chromium. The native IAB tool is unsupported in this Linux session; Playwright is the documented fallback.

Real HTTP browser harness is separate from fixtures: backend/tests/reporting/live_fixture.py seed|cleanup /tmp/<private-manifest>.json, test-only live_app.py with fixed2026-11-02 clock, frontend/playwright.live.config.ts and e2e/live-reporting.ts. APP_ENV=test plus the exact assigned disposable DSN is mandatory. Manifest credentials are random/mode0600 and never committed. Cleanup removes only recorded fixture UUIDs; ordinary database tests must not run while this committed dataset is present. Enable CADENTRA_LIVE_INVOICE_READY=1 only after adapters are integrated so 404/501 cannot silently skip a regression.

## Shared interfaces retained

Feature index modules export getRoutes():RouteObject[]; identity additionally exports getStaffRoutes(). Shared apiClient returns resource/list envelopes unchanged, uses same-origin cookies and authenticated X-CSRF-Token, supports cancellation and never silently retries mutations. Session/login shape remains {data:{actor:{id,name,role,customer_id},csrf_token}}.

Shared UI exports Button, PageHeader, DataTable, Money, DateLabel, StatusBadge, FormField, ConfirmDialog, EmptyState, ErrorPanel, LoadingSkeleton, SubscriptionStepper, ToastProvider/useToast. Use semantic tokens for both approved modes. Monetary formatting preserves decimal precision; service dates do not drift with browser timezone.

## Remaining role acceptance work

- T06: delegate invoice detail/escaped print and all lifecycle actions to the actual owner services; test foreign reads/prints/all mutations404, CSRF, safe nested projections, no mutation on failed access, scheduled effective dates and linked draft renewal.
- T28: current reporting SQL/HTTP reconciliation passes. Re-run integrated suite after owner merges and compare full real Overview including overdue table.
- T31: complete real product/variant/plan -> quotation -> active -> invoice -> payments2000.00+2970.16 -> report/portal reload/print journey. Owners' staff feature UIs and subscription workflow are not yet integrated. Four read cases do not establish this full journey.
- T30: explicit5000-subscription/20000-invoice plus payments dataset seeded and reconciled; measurements are running, no timing result claimed yet. Record commit/dirty state, environment, exact persisted counts, raw20warm+5fresh-context samples per ready route, browser/API p50/p95/max and all dependency gaps. Fresh browser contexts do not cold-start PostgreSQL/OS caches. Do not count placeholder/error pages as successful measurements.
- Only after required scope is green: optional CycleGuard and invoice explanation polish.

## Publishing and coordination

All application changes go through a feature PR targeting main; no direct main push. Coordinator serializes reviewed merges and maintains frozen docs/models/migrations. Incorporate reviewed main at least hourly; preserve atomic commits at least every30minutes during active work.

Existing author sherin745 <sherinsaji2006@gmail.com> is preserved. gh-agent4 authenticated GitHub as Sherin745. Git transport uses command-local ssh -F /dev/null -i "$HOME/.ssh/gh-agent4" -o IdentitiesOnly=yes -o BatchMode=yes; -F bypasses an unreadable system include. No global Git/SSH/OAuth account settings changed. The existing GitHub CLI account is9MidhunPM; use the coordinator's SSH-only PR-metadata fallback.

Prepared PR title: Add committed reporting and customer portal reads
Compare: https://github.com/9MidhunPM/Cadentra/compare/main...feature/reporting-portal
Description: Adds PostgreSQL-backed current/range metrics and zero-filled series, ownership-scoped customer portal reads, and the approved dark/light reporting and portal screens. Includes real cookie/API/PostgreSQL tests and separate unmocked browser evidence. Record the final tested head/check counts before publication. Lifecycle delegation, complete financial browser flow and large-data timings remain explicit follow-up requirements until verified.

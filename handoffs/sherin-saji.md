# Sherin Saji: handoff

Status: CUSTOMER LIFECYCLE SLICE GREEN; FULL BILLING JOURNEY AND FINAL BENCHMARK PENDING

Role: Experience & Reporting
Branch: feature/portal-lifecycle
Reviewed main: 382fa2b (subscription workflow, safe projections and invoice-period runtime)
Shared dialog focus recovery: 47195fe (coordinator-approved optional returnFocusRef)
Customer action delegation: e918b0c
Canonical lifecycle UI: 10eb6ef
Integrated sign-in/mobile progress verification: cbc7b6b
Reporting/portal backend: 2f33f9a
Reporting/portal frontend: 9edb851
Real browser harness: fcdfb7c
Delegated invoice detail/print: 53fd86b
Large-data measurement harness: 5bbdfd7
Latest reviewed-main merge: 3604b87
Performance evidence and reliable capture: 6ec57bb
Prepared full-journey harness: 776a780 (source checks only; browser execution pending)
Previous foundation PR2, themes PR5 and reporting/portal reads PR10 are integrated.
Setup verification commit: c4194af

## Delivered behavior

The user approved Graphite Mint as the primary/default dark theme and Sage Commerce as light mode. The references and visual/motion contract are in frontend/design/. The saved theme applies before first paint; browser theme-color now follows it. Shared navigation provides role-filtered Ctrl/Cmd K search, spring mobile navigation, tactile controls, safe route recovery, destination focus and reduced-motion support.

Reports read committed PostgreSQL data with Decimal totals serialized as strings. Summary uses one SQL statement for a consistent snapshot. Active subscriptions, outstanding and overdue are current-state metrics; invoice gross and actual payments use independent [from,to) date filters. Payment aggregation avoids invoice fanout. Revenue series supplies zero-filled DAILY or calendar MONTHLY buckets, clipped to the selected range and limited to 366 days. Midhun P M approved optional staff/admin customer_id on both summary and series on 31 October; only the coordinator edits the frozen API contract.

Overview now fetches real summary/series/overdue invoices, supports applied date/customer filters, exact accessible chart data, refresh and the owner's run-due endpoint. Displayed financial values remain server decimal strings. Numeric conversion is limited to approximate chart coordinates/axis labels. The mobile chart measures its container so labels retain readable size. Errors in independent resources remain visible.

Portal reads derive ownership from the authenticated CUSTOMER actor. Profile and paginated lists are scoped by that actor. Canonical subscription detail delegates to Thanushree Suresh; the temporary detail serializer was removed. Foreign detail returns404 and customer_id overrides are rejected. Invoice balances use grouped recorded payments, with separate collection_status and overdue values. Owner projections omit private fields, including nested metadata. Pagination rejects offsets exceeding PostgreSQL bigint limits.

Four explicit customer POST routes delegate pause/resume/close/renew to the subscription owner. The facade owns with db.begin(); ownership precedes semantic payload validation, including JSON arrays/scalars. No billing/policy/date logic is duplicated. Renewal returns a linked DRAFT requiring staff review. Invoice detail/escaped print remain delegated to Noel Biju with private/no-store and matching print headers.

The UI uses invoice_references, pause_interval, server effective dates, stored line totals, recurring subtotal/basis and tax previews. Only allowed_actions enables controls. Complete successful DTOs replace data with path/unmount guards; failures retain form inputs, late responses cannot redirect a later page, and removed action triggers return focus to a stable announced notice. Pending pause cancellation has explicit wording. Mobile lifecycle steps wrap so all five remain visible.

## Checks actually run

31 October 2026:

- Full backend on this slice and reviewed issuer baseline: **323 tests and 121 subtests pass**, real PostgreSQL at127.0.0.1:55431, cadentra_experience_test. Reporting includes17 service,19 report HTTP and70 portal cases. Ordinary tests roll back their outer transaction; committed race fixtures clean their own UUID graph.
- Reporting/backend Ruff: pass. Source fixtures exercise real login, cookie/session auth, roles, range/cadence validation, Decimal reconciliation, owner isolation, safe projections and PostgreSQL pagination bounds.
- Frontend full lint/test/build: **126 tests pass**, including15 portal and15 shared UI cases. Covers canonical dates/amounts, pause cancellation, conflict retention, linked-draft navigation, removed-trigger focus and late responses after navigation/unmount.
- Fixture browser suite: **24 desktop/mobile cases pass, two platform-specific skips**. This suite explicitly mocks session/business reads and proves shell/keyboard/theme/reduced-motion behavior, not database correctness.
- Separate live suite: **six desktop/mobile cases pass, no skips**, real HTTP/cookies/PostgreSQL with canonical subscription click/reload, report reconciliation and invoice detail/print isolation. A targeted mobile follow-up passes1/1 after the CSS fix, asserting all five lifecycle steps fully in viewport and no document overflow. No route interception or page errors. All exact-UUID fixture rows/private manifests removed and servers stopped.
- Delegated portal PostgreSQL tests: **70 pass**. Own pause/cancel/resume/close dates and linked-draft renewal persist; foreign/missing records share404 before invalid semantic bodies; role/CSRF/Origin/query guards and policy/due-billing failures leave state/audit/financial records unchanged. Invoice nested-address privacy, escaped print and read-only queries remain green. Owner sanitizers are reused unchanged.
- Report and portal screenshots inspected on desktop/mobile in the approved themes. Current portal captures are under /tmp/cadentra-live6-lifecycle-776a780-results/ and /tmp/cadentra-live-mobile-stepper-results/. These fictional fixtures do not establish the complete financial journey.
- Frontend build about524kB minified/161kB gzip plus separate95kB Motion features. Vite now reports a500kB chunk warning after owner screens were integrated; do not suppress it or interpret build size as latency. Final integrated timing remains pending.

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

Coordinator approved backward-compatible ConfirmDialog.returnFocusRef on31October. A connected stable target is used only if the original trigger disappears; ordinary Cancel/success focus remains unchanged. Tests cover both paths and failure input/focus retention.

## Remaining role acceptance work

- T06: delegated reads/print/actions and safe projections pass70 PostgreSQL cases and live read isolation. The prepared T31 scenario will additionally exercise all four own actions and foreign revision protection through real browser contexts.
- T28: reporting SQL/HTTP reconciliation and the full real Overview including the overdue table pass. Preserve these checks through later owner merges.
- T31: prepared real product/variant/plan -> quotation -> active -> invoice -> payments2000.00+2970.16 -> report/portal reload/print -> customer pause/cancel/close/linked Draft journey. The fixture term ends2027-01-02 so Dec2 remains an eligible future boundary. Execution waits the billing owner's corrected uncertain-payment UI; do not consume the earlier3076 UI head or call the prepared test passing.
- T30 historical baseline: **10 reporting/portal views,250 raw samples**,5000 subscriptions/20000 invoices plus payments. Complete Overview warm p50/p95/max511.3/556.7/565.8ms; full customer/date filter1224.0/1333.9/1372.4ms. The then-missing staff surfaces were honestly excluded. Final current-runtime/all-surface measurement is pending after T31. [Exact method, provenance and raw API/browser timings](../backend/tests/reporting/evidence/README.md). Fixtures/manifests were cleaned without dropping a database/schema.
- Only after required scope is green: optional CycleGuard and invoice explanation polish.

## Publishing and coordination

All application changes go through a feature PR targeting main; no direct main push. Coordinator serializes reviewed merges and maintains frozen docs/models/migrations. Incorporate reviewed main at least hourly; preserve atomic commits at least every30minutes during active work.

Existing author sherin745 <sherinsaji2006@gmail.com> is preserved. gh-agent4 authenticated GitHub as Sherin745. Git transport uses command-local ssh -F /dev/null -i "$HOME/.ssh/gh-agent4" -o IdentitiesOnly=yes -o BatchMode=yes; -F bypasses an unreadable system include. No global Git/SSH/OAuth account settings changed. The existing GitHub CLI account is9MidhunPM; use the coordinator's SSH-only PR-metadata fallback.

Prepared PR title: Delegate customer lifecycle actions with accessible updates
Compare: https://github.com/9MidhunPM/Cadentra/compare/main...feature/portal-lifecycle
Description: Reuses the subscription owner's safe query and transactional actions for customer pause/resume/close/renew. Canonical DTO updates preserve inputs, scheduled dates and focus; renewal remains a linked Draft. PostgreSQL/backend and frontend suites pass, with real desktop/mobile read/print proof. Full billing journey and final all-surface timings remain explicit follow-up gates.


## Parallel production frontend package

Branch: feature/frontend-production
Reviewed base: 48c7896 (isolated worktree; portal lifecycle work continues separately)
Implementation/evidence commit: 88da93d
Coordinator request: owned frontend static build/server on8080, SPA fallback, same-origin /api -> api:8001 with upstream404 preserved. Compose and runtime documentation remain Midhun P M's scope.

Added frontend/Dockerfile, nginx.conf and .dockerignore. Locked multi-stage Node build copies only dist into digest-pinned non-root NGINX1.30.6. API paths/query/header/body and error semantics are preserved; no API cache. Dynamic Docker DNS handles API replacement. HTML avoids stale chunk manifests; hashed assets get immutable cache and gzip, with real missing-asset404. Access logs are off; explicit no-referrer headers on both HTML locations prevent reset-link tokens entering upstream/error logs.

Executed: clean npm ci/build with unchanged lock, signed official native NGINX build/config validation, eight HTTP/DNS protocol checks, and real Chromium upstream-disconnect502 privacy proof with a policy-removed control. Independent review found the Referer logging issue; the fixed/control browser evidence proves its resolution while preserving Origin. Results and exact adaptations are committed under frontend/production-evidence/; official registry/signing/maintainer links are in its README.

Unverified: Docker build/entrypoint/user filesystem, actual Compose network/DNS and production deployment. Protocol fixtures are not successful real login/reset/billing evidence. All task-native servers stopped; no database/cloud/global-install operations performed by packaging.

Prepared PR title: Package the frontend for static same-origin serving
Description: Adds a locked production build and non-root static server on8080, preserving SPA links, API errors and authenticated headers. Native routing/DNS and Chromium referrer/error-path checks pass; Docker execution remains unverified. The coordinator wires Compose and runtime docs separately.
Compare: https://github.com/9MidhunPM/Cadentra/compare/main...feature/frontend-production

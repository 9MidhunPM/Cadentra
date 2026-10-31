# Sherin Saji: handoff

Status: FULL LOCAL BILLING/CUSTOMER JOURNEY PASSED; FINAL ALL-SURFACE BENCHMARK PENDING

Role: Experience & Reporting
Branch: feature/experience-validation
Journey runtime: reviewed mainff18b1f (billing, lifecycle, safe portal and static package integrated)
Passing journey/test-only focus correction: 41ef6df0521d853348803cd71471d5852b7bc313
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
Full-journey harness: 776a780, completed with test-only corrections/evidence in41ef6df
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
- T31 actual browser journey: **1/1 passed in16.6 seconds**, clean41ef6df at start/end, real Chromium/cookies/API/PostgreSQL, no request interception. Created catalog/config/template/subscription; quoted, confirmed and activated; generated exactly one4970.16 invoice; recorded2000.00+2970.16; verified PAID0.00 after reload; reconciled reports/portal; printed safely; executed customer pause/cancel/close/linked Draft renewal and foreign404/no-mutation checks. [Sanitized per-stage proof](../backend/tests/reporting/evidence/t31-2026-10-31.json).
- T31 processes stopped. Cleanup transaction rolled back at immutable rule-history DELETE guards; all guards remain enabled. The isolated fixture and private0600 manifest are preserved by coordinator decision. The paid-mobile PNG is a resize-transition frame, not settled visual evidence; subsequent mobile actions and the renewal capture are clear. Settled paid-invoice recapture will use the fresh benchmark namespace, without touching retained history.

## Runtime and reproducible evidence

Python3.12 backend environment is installed from the coordinator-owned frozen lock. Use assigned databases only:

- DATABASE_URL=postgresql+psycopg://cadentra@127.0.0.1:55431/cadentra_experience
- TEST_DATABASE_URL=postgresql+psycopg://cadentra@127.0.0.1:55431/cadentra_experience_test

The earlier experience_test now retains the immutable T31 journey history by coordinator decision. Do not run ordinary suites, seed again, or attempt cleanup there. Final T30 uses only cadentra_performance_test and its generated per-run namespace. Backend fixture guard tests do not connect to either database. Ruff remains .venv/bin/ruff check app/modules/reporting tests/reporting. Restricted-shell loopback is isolated, so native PostgreSQL/browser processes need the authorized host network execution context. No production migration, database reset/drop, or guard disabling was performed in this role.

Frontend commands from frontend/: npm run lint; npm test; npm run build. Vite binds5174 and proxies unchanged /api to API_PORT (default8004). PLAYWRIGHT_BROWSERS_PATH=/tmp/cadentra-agent4-browsers selects the installed pinned Chromium. The native IAB tool is unsupported in this Linux session; Playwright is the documented fallback.

Real HTTP browser harness is separate from fixtures: backend/tests/reporting/live_fixture.py seed|cleanup /tmp/<private-manifest>.json, test-only live_app.py with fixed2026-11-02 clock, frontend/playwright.live.config.ts and e2e/live-reporting.ts. APP_ENV=test plus the exact assigned disposable DSN is mandatory. Manifest credentials are random/mode0600 and never committed. Cleanup removes only recorded fixture UUIDs; ordinary database tests must not run while this committed dataset is present. Enable CADENTRA_LIVE_INVOICE_READY=1 only after adapters are integrated so 404/501 cannot silently skip a regression.

## Shared interfaces retained

Feature index modules export getRoutes():RouteObject[]; identity additionally exports getStaffRoutes(). Shared apiClient returns resource/list envelopes unchanged, uses same-origin cookies and authenticated X-CSRF-Token, supports cancellation and never silently retries mutations. Session/login shape remains {data:{actor:{id,name,role,customer_id},csrf_token}}.

Shared UI exports Button, PageHeader, DataTable, Money, DateLabel, StatusBadge, FormField, ConfirmDialog, EmptyState, ErrorPanel, LoadingSkeleton, SubscriptionStepper, ToastProvider/useToast. Use semantic tokens for both approved modes. Monetary formatting preserves decimal precision; service dates do not drift with browser timezone.

Coordinator approved backward-compatible ConfirmDialog.returnFocusRef on31October. A connected stable target is used only if the original trigger disappears; ordinary Cancel/success focus remains unchanged. Tests cover both paths and failure input/focus retention.

## Remaining role acceptance work

- T06: delegated reads/print/actions and safe projections pass70 PostgreSQL cases plus the full real-browser own/foreign lifecycle scenario. Revision, complete subscription-ID set, invoice and payment state remain unchanged after foreign attempts.
- T28: reporting SQL/HTTP reconciliation and the full real Overview including the overdue table pass. Preserve these checks through later owner merges.
- T31: **PASSED locally**, including the complete financial and customer-action journey. Source/method/status and all milestones are recorded in the sanitized evidence; no production deployment or external-delivery claim follows.
- T30 historical baseline: **10 reporting/portal views,250 raw samples**,5000 subscriptions/20000 invoices plus payments. Complete Overview warm p50/p95/max511.3/556.7/565.8ms; full customer/date filter1224.0/1333.9/1372.4ms. The then-missing staff surfaces were honestly excluded. Final current-runtime/all-surface measurement is pending after T31. [Exact method, provenance and raw API/browser timings](../backend/tests/reporting/evidence/README.md). Fixtures/manifests were cleaned without dropping a database/schema.
- Only after required scope is green: optional CycleGuard and invoice explanation polish.

Final T30 preparation uses the coordinator-approved new cadentra_performance_test and a fresh UUID run schema. Strict test guards retain APP_ENV=test, psycopg, cadentra user and127.0.0.1:55431; experience_test remains untouched. Test-only schema creation/migration and exact owned-namespace teardown follow the existing reviewed issuance-test pattern, with no production migration edits or guard disabling. This preparation is not a measured result yet.

## Publishing and coordination

The coordinator relayed the user's changed workflow on31October: owners integrate reviewed slices locally and push main with their own verified SSH keys only during an explicit serialized owner window. No API PR creation/merge, force push or deletion. Earlier PRs remain historical evidence. The coordinator maintains frozen docs/models/migrations; incorporate reviewed main at least hourly and preserve atomic commits at least every30minutes during active work.

Existing author sherin745 <sherinsaji2006@gmail.com> is preserved. gh-agent4 authenticated GitHub as Sherin745. Git transport uses command-local ssh -F /dev/null -i "$HOME/.ssh/gh-agent4" -o IdentitiesOnly=yes -o BatchMode=yes; -F bypasses an unreadable system include. No global Git/SSH/OAuth account settings changed; the existing API account is not used for owner integration.

Reporting read slice: feature/reporting-portal, head01c3acc, integrated through PR10 at48c7896. Delivered reconciled current/range metrics, zero-filled series, ownership-scoped reads and approved themes, with PostgreSQL/browser and historical timing evidence. Later lifecycle and final journey work is recorded separately below.

Reviewed lifecycle title: Delegate customer lifecycle actions with accessible updates
Reviewed feature head: 09d4a6238f06cc64363f15b279f758e71d685c03
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

## Production ingress identity hardening

Branch: feature/frontend-trusted-ingress; implementation and native evidence: 0306d16.
Reviewed main baseline: 0b131db. Coordinator requested a separate production configuration; development nginx.conf remains byte-identical (SHA256 96b4280b974063368fa06ef76b4caeee9d2ec7a8dfe6e2a2311bc3288325bb99).

CADENTRA_TRUSTED_INGRESS=true selects nginx.production.conf through the nonroot entrypoint. Unset/false selects development; all other values, including explicit empty, fail closed. The entrypoint writes only its /tmp runtime directory and leaves configuration files unchanged. Production trusts the exact original Traefik peer10.0.1.20, requires one valid CF-Connecting-IP and an actual realip rewrite, then overwrites X-Cadentra-Client-IP with the canonical address. It removes X-Forwarded-For, Forwarded, X-Real-IP and CF-Connecting-IP before the API. Static/SPA/cache/referrer behavior and Origin/Cookie/CSRF/API errors remain preserved. There is no HTTP health bypass.

Executed: 26 native NGINX1.30.6 realip checks, including raw duplicate/mixed-case CF headers, invalid/missing/comma/port addresses, canonical IPv6, spoofed internal headers, wrong original peer, no rewrite, SPA/assets/cache/gzip and nonroot selector tests. Shell syntax and whitespace checks pass. All task listeners stopped; no database touched. Exact source/binary hashes, command, adaptations and official build sources are in frontend/e2e/evidence/trusted-ingress-native.md and its JSON.

Integration dependency: production Compose must explicitly pass CADENTRA_TRUSTED_INGRESS=true; Midhun P M confirmed this in reviewed main. The coordinator owns the actual Cloudflare allowlist, exact private API peer and --no-proxy-headers configuration. Native protocol fixtures and immutable-source simulation do not verify Docker execution, a read-only root mount, real Traefik/Cloudflare, or deployment. Final T30 waits for the settled reviewed runtime.

## Applied customer overdue drilldowns

Branch: feature/reporting-drilldowns; reviewed base00ffa99
Implementation: bbb5ffc31160ab8204caf0109269fca58c9139d9

Both Overview overdue links retain only the applied customer_id. Unsubmitted customer/date edits do not affect navigation; from/to remain absent because overdue is current-state data. This pairs with Noel Biju's reviewed URL-filter support. No financial calculations, backend endpoints or policy changes.

Executed: red-before-fix regression, eight reporting tests, typecheck, scoped lint, production build and diff checks pass. Existing bundle warning remains recorded. No browser/database mutations performed by this slice. Ready for exact code review and a serialized owner SSH integration window.

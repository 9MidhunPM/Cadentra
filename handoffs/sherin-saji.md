# Sherin Saji: handoff

Status: FRONTEND FOUNDATION IMPLEMENTED AND TESTED; GATE A PENDING

Role: Experience & Reporting
Branch: feature/frontend-foundation
Setup commit: c4194af
Implementation commit: 158525d56aeddcf41f47ce55ce736f28234c8380
Baseline: 766cb2664ded48afcb1012001565cbbf65c68142

## Delivered slice

React/Vite/TypeScript frontend foundation: responsive staff/customer shells, role-aware navigation, stable feature entry points, same-origin API/session/error transport, reusable UI, design tokens, pinned dependencies, and unit/browser test configuration. All feature screens are explicitly unimplemented placeholders. No dashboard figures, financial operations or authentication backend are fabricated.

The initial placeholder files are the bootstrap exception documented in the role and architecture instructions. Identity/catalog, subscription and billing owners now replace their own placeholders; central routing does not need editing to add their feature routes.

## Files changed

Frontend build/dependency/test configuration; frontend/src/app/, components/ui/, lib/, styles/; initial frontend/src/features/*/index.tsx placeholders; frontend/e2e/foundation.spec.ts. No backend models, migrations, infrastructure or other contributors' handoffs changed.

## Shared interfaces for Gate A

Each feature's index.tsx exports getRoutes(): RouteObject[]. Identity additionally exports getStaffRoutes(): RouteObject[] for admin staff settings. This interface and the session response below were agreed with the coordinator's assistant during foundation work; combined runtime Gate A has not been verified.

Current route paths:

- Identity: /sign-in, /sign-up, /forgot-password, /reset-password; /settings/staff is admin only.
- Catalog: /customers, /catalog/products, /catalog/plans.
- Subscriptions: /subscriptions, /subscriptions/templates, /subscriptions/:id.
- Billing: /billing/invoices, /billing/invoices/:id, /billing/taxes, /billing/discounts.
- Reporting: /overview.
- Portal: /portal/subscriptions, /portal/subscriptions/:id, /portal/invoices, /portal/invoices/:id, /portal/account.

Frontend authorization is presentational; backend roles and ownership remain mandatory. Owners should use the relative import to shared libraries from their feature directory and add deeper routes inside their getRoutes factory.

frontend/src/lib exports:

- apiClient.request<T>(path, {method?, json?, headers?, signal?}) returns the documented JSON envelope unchanged. Paths are relative to /api/v1, for example /subscriptions. Cookies remain same-origin; authenticated mutations send X-CSRF-Token. Mutations are never silently retried.
- ResourceResponse<T>, ListResponse<T>, Actor, Role, Money (decimal string), SessionPayload and SessionStatus.
- ApiError with status/code/message/fields/requestId, getErrorMessage, isAbortError, createApiClient.
- SessionProvider and useSession(): {status, actor, error, refresh, logout}. Status is loading/authenticated/anonymous/error. Only 401 is anonymous; network/server/malformed responses remain errors. Protected API 401 clears stale displayed actors; stale/aborted requests and failed public login/reset calls cannot expire a newer session.
- Session/login handshake: {data:{actor:{id,name,role,customer_id},csrf_token}}. Roles uppercase; customer_id nullable UUID. Identity UI should call refresh after a successful login, not synthesize an actor locally.

frontend/src/components/ui exports Button, PageHeader, DataTable, Money, DateLabel, StatusBadge, FormField, ConfirmDialog, EmptyState, ErrorPanel, LoadingSkeleton, SubscriptionStepper, ToastProvider and useToast. Monetary formatting retains decimal-string precision. Dates display service dates without browser timezone drift. Confirmation failures preserve safe API explanations and keep the dialog open; unknown errors remain generic.

- Button: variant primary/secondary/danger, pending, standard button props.
- DataTable: columns [{key,header,render}], rows, getRowKey, page, pageSize, total, onPageChange; optional caption/emptyTitle.
- FormField: id, label, optional hint/error and one input/select/textarea child.
- ConfirmDialog: trigger element, title, description, confirmLabel and async onConfirm.
- useToast(): {toast(message, tone?)}; tone success/error/info.

## Run and check commands

From frontend/: npm ci; npm run dev. Default frontend port 5174, strict binding; /api is proxied unchanged to 127.0.0.1:${API_PORT}, default 8004. API_PORT may come from the process environment or a local repository-root .env. Example: API_PORT=8004 npm run dev. No environment values are embedded into the browser bundle beyond Vite's explicit public-variable convention.

npm run typecheck; npm run lint; npm test; npm run build. Build output: frontend/dist. Production SPA fallback and unchanged /api forwarding remain Midhun P M's infrastructure integration task.

Browser prerequisites: npx playwright install chromium. Then npm run test:e2e. Local verification used PLAYWRIGHT_BROWSERS_PATH=/tmp/cadentra-agent4-browsers and chromium --only-shell because the preinstalled browser revision did not match the pinned Playwright version. Run browser/server in the same network context; restricted shell loopback could not reach the other context's Vite server.

## Tests actually run

31 October 2026, against implementation 158525d:

- npm run typecheck: PASS.
- npm run lint: PASS, no warnings.
- npm test: PASS, 47 tests in three files (transport/session/UI).
- npm run build: PASS.
- npm run test:e2e: PASS, 13 desktop/mobile cases; one desktop instance intentionally skipped because it tests the mobile drawer only.
- npm install audit result after the explicit minimatch 11.0.1 override: zero known vulnerabilities. The override resolves the tooling-only glob advisory GHSA-g3hv-75wg-m249; lint/build/tests verify the selected baseline.
- git diff --check: PASS before implementation commit. Planning-pack check passed before implementation and again with this delivery handoff.

Unit checks cover money precision, service dates, pagination, form associations, dialog focus/error/retry behavior, session restoration/logout, CSRF, API errors, cancellations and stale-session races. Browser checks use clearly scoped test-only session fixtures: role navigation, direct restricted routes, anonymous redirect, logout CSRF, server-error recovery, persistence of routing on reload, no horizontal page overflow, and mobile Escape/focus return.

## Manual verification

Playwright Chromium screenshots inspected at 1440x1000 desktop and 390x664 mobile CSS viewport (mobile device pixel ratio 3). Checked navigation, typography, documented palette, responsive spacing and content clipping. The built-in browser operation is unsupported in this Linux session, so Playwright was the fallback. Test screenshots/reports remain ignored local artifacts.

This is frontend evidence with mocked session responses. Real PostgreSQL, backend auth/ownership, financial T06/T28, integrated T31 and seeded T30 performance tests have NOT RUN. No deployment or email delivery is claimed.

## Required shared changes and next dependency

Midhun P M integrates this foundation with the backend baseline, confirms real session/error envelopes and verifies migration/import/proxy startup before marking Gate A passed. Record the resolved frontend versions below in the coordinator-controlled decision register. No model or migration changes requested in this slice.

Proposed later revenue-series interface, not implemented/frozen yet: {data:{range_from,range_to,currency,cadence,buckets:[{period_start,period_end,invoiced_gross,cash_received}]}}; DAILY/MONTHLY calendar buckets, at most 366-day query range, decimal-string amounts, [from,to), default month-to-date. Coordinator should lock this before reporting implementation. Current-state metrics stay independent of the chosen range. Retained effective-dated tax/discount revisions do not require a shared-client change; reporting will use stored invoice dates/amounts.

## Resolved frontend baseline

Verified Node 26.12.1 and npm 12.2.1; package engines require Node >=22.12. React/React DOM 19.3.1, React Router 8.5.1, Vite 8.3.5, TypeScript 6.0.3, Tailwind 4.3.3, Radix Dialog 1.3.1, Vitest 5.0.5, Playwright 1.64.1. All dependencies pinned exactly in frontend/package.json and package-lock.json; backend versions remain coordinator-owned.

## Publishing and workspace verification

Initial setup commit c4194af was pushed successfully using the existing gh-agent4 SSH key; GitHub identified Sherin745. Existing author configuration was preserved. Commands use IdentitiesOnly=yes and a command-local -F /dev/null bypass because the system SSH include is unreadable. No global authentication settings changed. Commits use the configured Git identity; SSH authenticates transport.

The GitHub CLI's existing account is 9MidhunPM, not Sherin745. Do not switch it globally. Follow the documented fallback: provide the tested branch/comparison and prepared PR description to Midhun P M for PR creation.

PR title: Add the shared frontend foundation
Compare: https://github.com/9MidhunPM/Cadentra/compare/main...feature/frontend-foundation
PR description: Adds the responsive staff/customer shell, agreed feature route exports, cookie/CSRF session client, shared accessible controls and locked frontend tooling. Build/typecheck/lint, 47 focused tests and 13 fixture-backed browser cases pass. Business screens remain explicit placeholders; integrated backend/PostgreSQL Gate A is pending. Initial feature placeholders transfer to their assigned owners after integration.

Atomic commits are required at least every 30 minutes during active work; setup and implementation commits were less than eight minutes apart.

## Next slice

Deliver this foundation for review and Gate A integration. After it is integrated and verified, start feature/reporting-portal from reviewed origin/main. Reporting/portal business logic and optional CycleGuard have not started.

# Sherin Saji: Experience & Reporting

Read the repository-root AGENTS.md first. Work on behalf of Sherin Saji within this role; this assignment does not change Git identity or authorize impersonation. This file adds scope to shared instructions.

Initial feature branch: `feature/frontend-foundation`. In your assigned independent clone, follow the root startup checks, fetch origin, and create this branch from reviewed origin/main. Keep an existing branch only after inspecting it. Deliver through a PR targeting main; follow the root fallback if PR creation is unavailable.

## Owned paths
frontend/src/app/, frontend/src/components/ui/, frontend/src/lib/, frontend/src/styles/, frontend build/dependency manifests, frontend/src/features/reporting/ and portal/.
backend/app/modules/reporting/, backend/tests/reporting/, frontend/e2e/ configuration and reporting/portal tests, handoffs/sherin-saji.md.

## Mission
Create one coherent product shell, share reusable controls, implement real reporting and customer portal, and exercise the integrated browser journey. Other team members build their own feature screens inside their scopes; do not become the only frontend writer.

## First job: frontend foundation
The documentation baseline is enough to start this work while Midhun P M builds the backend. Full reporting/portal implementation waits for the integrated Gate A baseline. Open the foundation PR first; use feature/reporting-portal for the next slice after integration.
Coordinate a same-origin /api transport with Midhun P M. Create app shell, route placeholders importing stable feature exports, API/error/session client, reusable forms/tables/dialogs/status labels and design tokens. Supply these before other team members implement feature screens. Do not implement duplicate backend auth or an in-memory final app.

## Delivery sequence
1. Gate A frontend shell, feature placeholders, shared types/client/components, coherent navigation and role-aware display.
2. Reporting queries for current active count, invoiced amounts, actual payments, outstanding/overdue, filters and series.
3. Customer portal data routes with server ownership checks, safe invoice printing and delegated lifecycle actions.
4. End-to-end browser test, desktop/mobile checks, complete-flow integration and seeded performance measurement.
5. Only after required scope is green: CycleGuard and invoice explanation polish.

## Required behaviours
All metrics come from committed database records. Keep current-state metrics distinct from date-range metrics. No fabricated MRR, bank reconciliation, forecast or AI certainty. Customer routes derive customer ID from auth, never request selection. Use Thanushree Suresh/Noel Biju services for actions/printing; no duplicate business rules.

Frontend authorization is presentational only. Test direct API attempts to other customers' IDs. Include loading/empty/error/forbidden states and accessible forms. Do not show a live payment button when only manual staff entry exists.

## Tests and done
T06, T28, T30, T31, with evidence from real PostgreSQL and the browser. Verify reload persistence, client error mapping, page widths and printable invoice. Record timing environment and actual samples; no unmeasured <2s claims. Report design defects to feature owners rather than editing their files without a handoff.

## Exclusions
No migration/model edits, no reinitialization of Midhun P M's backend, no global credential changes, no static production dashboard JSON, no late redesign, no remote publishing outside the approved process.

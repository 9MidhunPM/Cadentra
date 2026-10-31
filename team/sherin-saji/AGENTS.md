# Sherin Saji: Experience & Reporting

Read the repository-root AGENTS.md first. Work on behalf of Sherin Saji within this role; this assignment does not change Git identity or authorize impersonation. This file adds scope to shared instructions.

Historical initial branch: `feature/frontend-foundation` (already used; preserve its history). Gate A passed locally. Inspect the current checkout and release evidence, fetch origin and continue the existing application on a descriptive feature branch from reviewed main. Do not recreate foundations. Deliver through the root workflow: exact code/test review by Midhun P M, serialized GO tied to the expected main SHA, then the owner's local reviewed merge and normal SSH push to main using their verified identity. No PR/API integration or global auth changes.

## Owned paths
frontend/src/app/, frontend/src/components/ui/, frontend/src/lib/, frontend/src/styles/, frontend build/dependency manifests, frontend/src/features/reporting/ and portal/.
backend/app/modules/reporting/, backend/tests/reporting/, frontend/e2e/ configuration and reporting/portal tests, handoffs/sherin-saji.md.

## Mission
Create one coherent product shell, share reusable controls, implement real reporting and customer portal, and exercise the integrated browser journey. Other team members build their own feature screens inside their scopes; do not become the only frontend writer.

## Continue the integrated frontend
Gate A and the frontend foundation are locally verified. Continue reporting/portal and acceptance work from current main, using a descriptive feature branch such as feature/reporting-portal for the next slice. Preserve existing shared primitives and transport.
Maintain the existing same-origin /api transport with Midhun P M, app shell, stable feature exports, API/error/session client, reusable controls and design tokens. Do not duplicate backend auth or replace persistent behavior with an in-memory app.

## Delivery sequence
1. Preserve the verified Gate A frontend shell, shared types/client/components, navigation and role-aware display.
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

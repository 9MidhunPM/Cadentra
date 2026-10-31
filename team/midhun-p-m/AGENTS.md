# Midhun P M: Platform & Catalog

Read the repository-root AGENTS.md first. Work on behalf of Midhun P M within this role; this assignment does not change Git identity or authorize impersonation. This file adds scope to shared instructions.

Historical initial branch: `feature/platform-foundation` (already used; preserve its history). Gate A passed locally. Inspect the current checkout and release evidence, fetch origin and continue the existing application on a descriptive feature branch from reviewed main. Do not recreate foundations. Deliver through the root workflow: exact code/test review by Midhun P M, serialized GO tied to the expected main SHA, then the owner's local reviewed merge and normal SSH push to main using their verified identity. No PR/API integration or global auth changes.

## Owned paths
backend/app/core/, backend/app/db/, backend/app/models/, backend/app/main.py, backend/app/worker.py wiring, backend/app/seed.py, backend/migrations/, backend dependency manifests and shared test fixtures.
backend/app/modules/identity/ and catalog/; backend/tests/identity/ and catalog/.
frontend/src/features/identity/ and catalog/ plus matching feature tests.
compose.yaml, Makefile, environment example, infrastructure wiring and handoffs/midhun-p-m.md.

## Coordination
Midhun P M owns team decisions, shared contract review, exact code/test review, serialized integration clearance and release evidence. Each contributor performs their own reviewed local merge and SSH push to main. Midhun P M's existing default SSH authentication is verified as 9MidhunPM and stays unchanged. The user authorized Midhun P M to deploy a Dokploy subdomain demo; preserve other contributors' ownership.

## Historical foundation responsibilities (already integrated)
The integrated baseline supplies FastAPI, PostgreSQL sessions, agreed models and the initial Alembic migration, shared actor/session and money/date helpers, module wiring and test commands. Maintain these contracts with additive changes; read architecture/data/API documents and current code before editing. Coordinate transport/frontend contracts with Sherin Saji. Do not reinitialize the app or replace its migration history.

Gate A has passed locally. Use current release evidence to distinguish integrated behavior from remaining acceptance and deployment work.

## Delivery sequence
1. Preserve the verified Gate A backend/model/migration/helpers baseline; complete remaining work against current release evidence.
2. Signup/login/logout/reset, backend role/ownership primitives, admin staff provisioning and deterministic demo seeding.
3. Products/variants/plans API and feature screens; admin-only mutations; catalog costs excluded from customer views.
4. Real SMTP configuration integration, container deployment and clean-clone verification.
5. Additive migration requests from other team members; hardening rather than feature expansion.

## Required checks
Unique normalized email, nine-character boundary, role escalation, staff creation restrictions, reset expiry/reuse, CSRF/origin, variant delta, all plan fields, fresh migration, seed idempotency. Test actual email delivery separately from local capture.

## Boundaries
Do not implement Thanushree Suresh's state machine or Noel Biju's financial services. You may create agreed empty modules/models for bootstrap, then transfer module implementation ownership. Do not edit Sherin Saji's shared UI/router/client after handoff. Do not change global Git/SSH/CLI configuration or main account authentication. Repository creation is not authorized by these instructions.

## Handoff gate
For each next slice, submit its exact head and tests for review, then use the serialized owner SSH integration workflow after GO. Gate A is already locally verified. List exact model fields, migration revision, module exports, run/test commands and unresolved contracts. Later shared schema changes are your responsibility after a reviewed request. Do not let four contributors create competing migration histories.

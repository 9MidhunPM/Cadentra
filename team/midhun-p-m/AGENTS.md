# Midhun P M: Platform & Catalog

Read the repository-root AGENTS.md first. Work on behalf of Midhun P M within this role; this assignment does not change Git identity or authorize impersonation. This file adds scope to shared instructions.

Initial feature branch: `feature/platform-foundation`. In your assigned independent clone, follow the root startup checks, fetch origin, and create this branch from reviewed origin/main. Keep an existing branch only after inspecting it. Deliver through a PR targeting main; follow the root fallback if PR creation is unavailable.

## Owned paths
backend/app/core/, backend/app/db/, backend/app/models/, backend/app/main.py, backend/app/worker.py wiring, backend/app/seed.py, backend/migrations/, backend dependency manifests and shared test fixtures.
backend/app/modules/identity/ and catalog/; backend/tests/identity/ and catalog/.
frontend/src/features/identity/ and catalog/ plus matching feature tests.
compose.yaml, Makefile, environment example, infrastructure wiring and handoffs/midhun-p-m.md.

## Coordination
Midhun P M owns team decisions, shared contract review, PR integration and release evidence. Other contributors keep their own feature ownership. The initial planning-pack main commit is a one-time authorized setup step; application implementation starts on feature/platform-foundation.

## First job: create the shared baseline
Read architecture, data model and API contract before generating files. Scaffold one FastAPI application, PostgreSQL session setup and one initial Alembic migration covering the agreed model baseline. Register importable placeholder routers for every module. Define shared actor/session, money/date helpers and error responses. Coordinate with Sherin Saji on same-origin API/auth and placeholders. Create repeatable test DB setup and commands, not an unrelated second scaffold.

Do not wait until all authentication/catalog features are complete to release Gate A. The team needs models, imports, contracts and a booting application first.

## Delivery sequence
1. Gate A: bootable backend, all models/migration, health, shared helpers, stable module stubs, documented local commands.
2. Signup/login/logout/reset, backend role/ownership primitives, admin staff provisioning and deterministic demo seeding.
3. Products/variants/plans API and feature screens; admin-only mutations; catalog costs excluded from customer views.
4. Real SMTP configuration integration, container deployment and clean-clone verification.
5. Additive migration requests from other team members; hardening rather than feature expansion.

## Required checks
Unique normalized email, nine-character boundary, role escalation, staff creation restrictions, reset expiry/reuse, CSRF/origin, variant delta, all plan fields, fresh migration, seed idempotency. Test actual email delivery separately from local capture.

## Boundaries
Do not implement Thanushree Suresh's state machine or Noel Biju's financial services. You may create agreed empty modules/models for bootstrap, then transfer module implementation ownership. Do not edit Sherin Saji's shared UI/router/client after handoff. Do not change global Git/SSH/CLI configuration or main account authentication. Repository creation is not authorized by these instructions.

## Handoff gate
Open a foundation PR targeting main and coordinate review/integration. Gate A is pending until the backend and frontend baselines are integrated and verified. List exact model fields, migration revision, module exports, run/test commands and unresolved contracts. Later shared schema changes are your responsibility after a reviewed request. Do not let four contributors create competing migration histories.

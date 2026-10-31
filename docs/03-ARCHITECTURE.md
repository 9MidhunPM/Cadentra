# Architecture and ownership

## Approved stack

React + Vite + TypeScript for a client-side app; Tailwind plus a small accessible component library; FastAPI + Pydantic + SQLAlchemy + Alembic; PostgreSQL; a standalone Python worker using the same application services; Docker Compose for repeatable local deployment. The user approved this stack on 31 October 2026. Select compatible versions at bootstrap, commit lockfiles and freeze them. No Redis, separate microservices or extra job platform is needed for this scope.

This intentionally revises the earlier Next.js suggestion. It avoids splitting auth and billing across a frontend server and FastAPI. The proposed application does not need marketing-page rendering. If the team keeps Next.js instead, record that before Gate A and preserve the same backend/domain contracts; never run two competing scaffolds.

## Process layout

```text
Browser
  -> same-origin frontend / reverse proxy
       /api/v1/* -> FastAPI -> PostgreSQL
       /*        -> built client SPA
Standalone worker -> same domain services -> PostgreSQL
Mail outbox worker -> configured SMTP service
```

The Vite development proxy forwards /api to FastAPI. Production reverse proxy must forward /api unchanged and serve the SPA fallback for client routes. PostgreSQL is not publicly exposed. The scheduler is not launched inside every API process. Financial jobs use database constraints/locks even if only one worker is configured.

## Repository layout to create at bootstrap

```text
backend/
  app/
    main.py                    # Midhun P M: mounts the agreed feature routers
    core/                      # settings, auth dependencies, money/date helpers
    db/                        # engine, session, Base
    models/                    # Midhun P M owns all ORM models
    modules/
      identity/                # Midhun P M
      catalog/                 # Midhun P M
      subscriptions/           # Thanushree Suresh
      billing/                 # Noel Biju
      reporting/               # Sherin Saji
    worker.py                  # Midhun P M wiring; Noel Biju job implementation
    seed.py                    # Midhun P M deterministic seeded data
  migrations/                  # Midhun P M exclusively
  tests/
    identity/ catalog/         # Midhun P M
    subscriptions/             # Thanushree Suresh
    billing/                   # Noel Biju
    reporting/                 # Sherin Saji
frontend/
  src/
    app/                       # Sherin Saji routing and shell
    components/ui/             # Sherin Saji shared primitives
    lib/                       # Sherin Saji fetch/error/session client
    features/
      identity/ catalog/       # Midhun P M
      subscriptions/           # Thanushree Suresh
      billing/                 # Noel Biju
      reporting/ portal/       # Sherin Saji
    styles/                    # Sherin Saji
  tests/                       # role-owned tests in matching subfolders
  e2e/                         # Sherin Saji configuration, role-owned test files
contracts/                     # coordinator-controlled after Gate A
team/ prompts/ handoffs/ docs/
compose.yaml Makefile .env.example
```

## Gate A interface commitments

All backend feature modules export `router` from router.py and use a shared `get_session` and `require_role` dependency. Midhun P M registers placeholders once. All frontend features export a route-element factory through their own index.tsx. Sherin Saji registers the placeholder imports once. Feature owners replace their placeholders in place without editing central routing. Identity and catalog features may export separate route arrays.

Use synchronous SQLAlchemy Session objects and request-scoped sessions consistently across backend modules; financial services explicitly own their transactions.

Shared money helper: quantize Decimal to 0.01 with ROUND_HALF_UP. Shared clock: `today()` in configured business timezone, backed by an injected test clock. Shared error shape and list envelopes follow the API contract. Shared session dependency returns actor user ID, role and customer ID.

## Service boundaries

Subscriptions validates lifecycle and exposes `process_lifecycle(db, as_of)` and read-only pricing inputs for billing. Billing owns calculation, due-cycle issuance, invoice transitions, discounts, tax rules and payments. Reporting reads committed records; it never recalculates invoice values from catalog prices. Identity alone creates sessions/reset tokens. The worker calls lifecycle processing then billing then outbox dispatch. Contract details are in `docs/05-API-CONTRACT.md`.

Avoid circular service imports. Activation does not call billing synchronously; a worker tick or the operator's run action generates the first due invoice. The UI can poll the resulting invoice list.

## Database ownership protocol

Midhun P M creates every agreed ORM model and the initial migration before domain writers begin implementation. A feature owner needing a new field posts an explicit change request with type, nullability, default and rationale in its handoff file. Midhun P M implements the reviewed additive migration. Never create independent Alembic heads or use create_all as a substitute for migrations.

## Workspace isolation

Use separate clone folders, virtual environments, frontend dependency folders, databases, Compose project names and ports. Example project names: cadentra-platform, cadentra-subscriptions, cadentra-billing and cadentra-experience. Example web ports: 5171-5174; API: 8001-8004; PostgreSQL: 5433-5436 if host-bound at all. These are proposed values; check occupancy first. .env.example starts with the platform workspace; use distinct database names and ports for the other workstreams. Each test worker must use an explicitly disposable test database. No team member runs migrations or seeds against another team member's database.

## Operational design

An SMTP outbox stores recipient, subject, template payload, attempt count, status and last error. Reset tokens/credentials are never logged. Sending is at-least-once at the transport boundary: SMTP acknowledgement loss can duplicate an email, but must never duplicate an invoice/payment. Do not promise exactly-once external email delivery. Success states distinguish queued, accepted-by-SMTP and delivery-tested.

Deploy a working slice early; schema/seed/auth integration is the critical path. Do not wait for a finished frontend to discover the API container cannot connect to PostgreSQL.

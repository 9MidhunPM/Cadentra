# Runtime and repeatable setup

The foundation uses one API, PostgreSQL, and one explicitly enabled standalone worker. The frontend foundation is owned by Sherin Saji. Foundation readiness is not proof of a complete billing, portal or email workflow.

## Compose startup

Prerequisites: Docker Engine with Compose v2; local .env copied from .env.example. Replace placeholder passwords locally; use a URL-safe database password because the composed DATABASE_URL interpolates it into a URL. Never commit .env. Use a unique COMPOSE_PROJECT_NAME and database per workspace.

```sh
cp .env.example .env
# Edit .env locally before continuing.
make dev
```

Compose waits for PostgreSQL, applies Alembic migrations once through the migrate service and starts the API. The database publishes no host port; API binds loopback at API_PORT (default 8001). A production reverse proxy must connect to the API network without making PostgreSQL public. The PostgreSQL 18 volume is mounted at /var/lib/postgresql, matching the image layout. No command removes volumes.

In a second terminal, after the frontend foundation is integrated:

```sh
npm --prefix frontend ci
make frontend-dev
make smoke
```

Vite forwards /api unchanged to the configured API_PORT. Browser requests use the frontend origin; cookies and CSRF remain same-origin. Production frontend assets and proxy belong to the frontend foundation/release integration and are not fabricated by this backend image.

Worker activation is explicit after the lifecycle, billing and outbox services are integrated:

```sh
make worker
```

Before those services exist this command exits with a clear unavailable-service error. It does not idle and pretend to process financial jobs. Only one worker service should be active. Restarting it relies on each financial service's committed period keys/row locks, not on the process being unique. The worker never starts inside an API process.

## Native PostgreSQL path

Docker is optional when a reachable isolated PostgreSQL instance is supplied. Python 3.12 and uv are required. Set DATABASE_URL to your own application database, TEST_DATABASE_URL to a separate disposable test database, and the other settings from .env.example. The native API reads local settings; never print real connection credentials.

```sh
make sync
make native-migrate
make backend-dev
# Separate terminal, once domain services are integrated:
make worker-native
```

A task-owned PostgreSQL runtime extracted under /tmp may provide the test service when no container engine is available. Verify package signatures and linked libraries first; create a fresh cluster owned by the current user, use a private socket directory and an unused loopback port. Local temporary trust authentication is for this disposable cluster only. No native script installs packages globally or modifies the user's existing databases. Exact runtime versions, directory/port, commands and outcomes belong in the handoff that performed that verification.

## Demo seed

Seeding requires an explicit --demo flag and local DEMO_ADMIN_EMAIL/DEMO_ADMIN_PASSWORD. It creates a fictional admin and canonical product/variant/monthly plan using stable IDs in one transaction. Repeating it creates no duplicates, preserves existing prices/passwords, and refuses to promote a pre-existing non-admin email. It does not manufacture invoices, payments, deliveries or complete subscription flows.

```sh
make seed-demo
# Or against a deliberately selected native demo database:
make seed-demo-native
```

The database and SMTP credentials stay local. Development mail capture is not external delivery. Configure the real SMTP endpoint and verify reset/invoice delivery separately before marking those requirements complete.

## Checks and evidence

```sh
make lint
make test
make smoke
```

The test target runs pack checks and backend tests, then frontend tests if the frontend exists. PostgreSQL tests require the separate TEST_DATABASE_URL. Missing frontend or unrun database tests must remain explicit in evidence. Smoke checks actual API/database readiness only; it does not prove browser, billing-concurrency, email or deployment correctness. Fresh-clone setup must use committed dependency locks and migrations.

## Resolved container references

The Dockerfile pins Python 3.12.13 and uv 0.12.9; PostgreSQL is pinned to 18.6-bookworm. Image builds and Compose execution require a Docker-capable environment and must be recorded separately from native checks. The supported PostgreSQL 18.6 image/tag and volume convention were checked against the [official image documentation](https://hub.docker.com/_/postgres); uv installation follows [its Docker guide](https://docs.astral.sh/uv/guides/integration/docker/). Do not label the container build as verified until it actually runs.

## Verified local Gate A check

With the frontend proxy and API running against an explicitly disposable local demo database, run `node scripts/check_gate_a.mjs`. Install Playwright Chromium first, or set PLAYWRIGHT_CHROMIUM_EXECUTABLE to a compatible installed Chromium. The check only accepts localhost/127.0.0.1 HTTP origins (GATE_A_ORIGIN defaults to http://localhost:5171), creates one fictional customer, verifies real cookie/CSRF/role/session behavior through the proxy and checks customer navigation. Set GATE_A_SCREENSHOT for a local evidence image. It does not prove the full subscription/payment workflow.

The full `make test` requires TEST_DATABASE_URL and refuses to report a complete suite with the PostgreSQL tests silently omitted. Native Gate A was verified with PostgreSQL18.6, migrations0001 and0002, real browser proxy requests and locked frontend build/tests. Docker execution and external SMTP delivery remain unverified.

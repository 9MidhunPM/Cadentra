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

Worker activation is explicit; the integrated lifecycle, billing and outbox services run in one supervised Compose service:

```sh
make worker
```

The worker validates its service exports before performing a tick and exits clearly if an integration is missing. Compose supervises this explicitly selected service with restart: unless-stopped. Repeating make worker reuses the same service instead of creating a second one-off process. Keep one replica and do not additionally run worker-native against the same workspace. Financial correctness still relies on committed period keys and row locks. The worker never starts inside an API process.

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

## Mail capture and real SMTP configuration

Compose includes pinned `axllent/mailpit:v1.33.0` for development captures of reset and invoice emails. `make dev` starts it with the API; `make mail-up` starts only capture. Its inbox binds `127.0.0.1:${MAILPIT_WEB_PORT:-8025}` and SMTP binds `127.0.0.1:${MAILPIT_SMTP_PORT:-1025}`. Neither listener is public. No external relay/forwarding is configured. The development inbox contains sensitive reset links; keep it local and out of shared screenshots.

Native applications default to SMTP_HOST=localhost and SMTP_PORT=1025. Compose overrides SMTP_HOST using COMPOSE_SMTP_HOST, default mailpit; port/user/password/from/TLS use the configured SMTP environment. A real provider can be selected with COMPOSE_SMTP_HOST (Compose) or SMTP_HOST (native), SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM and SMTP_STARTTLS. Supply credentials locally. No real provider or external delivery is assumed by this capture setup.

After a reset/invoice operation queues a message, dispatch one actual batch:

```sh
make outbox-native
# Compose equivalent:
make outbox
```

The explicit `python -m app.core.outbox --once [--limit N]` command commits one caller-owned transaction and prints processed, accepted_by_smtp and failed counts only. SMTP acceptance is not external delivery. Dispatch returns nonzero if the batch contains failed deliveries; retry scheduling remains recorded by the dispatcher. The complete lifecycle worker is not required for this mail-only operation.

Open the inbox at http://127.0.0.1:8025 (or MAILPIT_WEB_PORT). Verify the intended fictional recipient, subject, content and actual reset/invoice action. Capture evidence must distinguish composition, SMTP acceptance, web inbox visibility, and external delivery. External delivery remains skipped until a real provider is configured and tested.

For systems without Docker, the official native release can run from a task-owned temporary directory after verifying its published SHA-256 digest. Bind both listeners explicitly to loopback, set a task-owned database, and disable version checks/reverse DNS. Stop the native server before using Compose on the same ports. The native launch used for this integration was `/tmp/cadentra-mailpit-1.33.0/mailpit --database /tmp/cadentra-mailpit-1.33.0/mailpit.db --listen 127.0.0.1:8025 --smtp 127.0.0.1:1025 --disable-version-check --smtp-disable-rdns`. The pinned version and binary checksum came from the [official release](https://github.com/axllent/mailpit/releases/tag/v1.33.0); container tag conventions and ports follow the [official Docker guide](https://mailpit.axllent.org/docs/install/docker/). This does not verify a Docker build or external email delivery.


## Immutable frontend and full application packaging

After the reviewed frontend-production package is integrated, the optional web profile builds frontend/Dockerfile from the frontend directory, installs its committed npm lock and copies only built assets into the digest-pinned non-root NGINX image. Port8080 inside the image maps only to loopback WEB_PORT (default5171). NGINX sends /api unchanged to api:8001, preserves API errors and authentication headers, and uses Docker DNS to handle API replacement. Neither PostgreSQL nor Mailpit is made public.

```sh
# Immutable web frontend plus healthy API/database/migrations/mail capture:
make web
# The same stack plus exactly one supervised financial/outbox worker:
make full-app
```

The default make dev remains the API/native-Vite development path. The web profile is optional and never starts merely because make dev runs. The worker profile is also explicit; full-app selects both profiles. Both web and worker use unless-stopped supervision after selection. No target scales services, deletes volumes or changes another project's containers.

Set APP_ORIGIN and ALLOWED_ORIGINS to the exact browser origin, including WEB_PORT when using local HTTP, and keep SESSION_COOKIE_SECURE=false only for that local development path. Defaults are http://localhost:5171; changing WEB_PORT without updating the origin settings breaks session-origin/CSRF checks. Rebuild/recreate configured services after changing environment. For an authorized HTTPS deployment behind an external reverse proxy, use the real HTTPS APP_ORIGIN/ALLOWED_ORIGINS, APP_ENV=production and SESSION_COOKIE_SECURE=true. The loopback web binding is deliberate; this task does not modify host routing, firewall, cloud services or domains. Configure real SMTP locally before claiming external delivery.

Frontend production routing/reference evidence is committed under frontend/production-evidence/ by its owner: native NGINX checks cover SPA links, immutable assets, API errors, request headers and dynamic upstream DNS. Password-reset query tokens are protected with no-referrer HTML headers and disabled frontend access logging. Those protocol fixtures and native checks do not verify image build/entrypoint permissions or actual Compose networking. Docker execution remains UNVERIFIED until a Docker-capable environment runs the exact integrated commit.

## Dokploy deployment artifact

`compose.dokploy.yaml` is the root-level deployment variant for the authorized demo; `compose.yaml` remains local development packaging. Select the Git repository/root and `./compose.dokploy.yaml` in Dokploy. All seven services run without profiles: PostgreSQL, capture, migration, demo bootstrap, API, one worker and static web. None publishes a host port. Dokploy's HTTPS domain targets only web:8080; other services stay on the private application network. No capture inbox is public.

Use Dokploy's private environment for exact HTTPS APP_ORIGIN/ALLOWED_ORIGINS, URL-safe database credentials, generated fictional admin credentials, and optional real SMTP settings. Production mode and secure cookies are enforced by the artifact. Bootstrap starts after migration and must finish successfully before API/worker; it is idempotent and prints creation counts rather than credentials. Admin credentials are injected only into bootstrap. Retained PostgreSQL/capture volumes survive redeployments; no cleanup/reset is automatic. Changing the seeded password environment does not rotate an existing account's password.

A host equivalent is `docker compose --env-file <private-env-file> -f compose.dokploy.yaml up --build -d`. Actual build/Traefik/TLS/startup/session/financial-flow checks remain the coordinator's deployment evidence; the presence of this artifact alone is not a deployment result. See docs/12-DEPLOYMENT.md for the target-domain procedure.

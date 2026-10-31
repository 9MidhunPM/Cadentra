# Deployment and runtime checklist

Proposed single-host deployment using Docker Compose, compatible with an existing reverse-proxy platform such as the user's Dokploy/Traefik environment. The user has authorized the demo: a separate Cadentra Dokploy project andcadentra.midhunpm.in domain are prepared; actual deployment/live verification is pending. No unrelated service or wildcard routing was changed. Do not modify live wildcard routing or other services without explicit approval.

## Required services

Frontend static build served with SPA fallback; FastAPI API; PostgreSQL on an internal network; standalone lifecycle/billing/outbox worker. Development may include local SMTP capture. Deployment requires a configured real SMTP service to satisfy external-email flows.

## Environment contract

Read the provided `.env.example`; replace all placeholder values locally. Production uses a unique database password, stable application origin, Secure session cookies, allowed origin, business timezone/currency, SMTP host/port/user/password/from address, and a worker polling interval. Pin container/dependency versions at bootstrap. Avoid floating latest tags after the baseline is established.

## Bootstrap requirements

Midhun P M must implement: one documented startup path, migrations, idempotent demo seed, readiness/health endpoint, a standalone worker, Make targets and a deployment readme. Sherin Saji implements production frontend asset build and /api proxy compatibility. No assumptions about preinstalled host packages; document exact resolved versions.

## Deployment sequence

Build artifacts and run tests; start PostgreSQL; apply reviewed migrations once; seed only if explicitly requested for a demo database; start API/frontend; verify cookie/origin routing; start exactly one configured worker; execute the smoke test through the public origin. The database and admin credentials must not be public.

Test logout, reset link origin, invoice print authorization, worker catch-up, payment persistence after restart and email queue failure reporting. An API healthcheck alone is not deployment verification.

## Failure behavior

Worker retries uncommitted due cycles; unique keys prevent duplicate financial records. SMTP outage stores a failed/retriable delivery and does not block invoice persistence. API/database errors surface useful UI errors rather than fake success. Avoid scheduler startup in every API replica.

## Safety

Never run docker compose down -v, drop a database or seed into a non-demo environment without explicit confirmation. Back up data before destructive changes. Do not expose Mailpit/capture inboxes publicly. Do not commit .env, credentials or tokens. Keep existing project/domain routing untouched.

## Completion record

Record deployed commit, exact URLs, health/smoke outcomes, service versions, migration revision, demo seed status, external-email result and known limitations. If only local deployment works, say so.


## Packaged local stack

The optional web Compose profile builds the reviewed immutable frontend/Dockerfile and serves its non-root8080 port at loopback WEB_PORT. It waits for the API healthcheck; NGINX proxies /api unchanged to api:8001. `make web` starts that web/API stack. `make full-app` additionally enables the explicit worker profile with exactly one supervised worker. `make dev` retains the separate Vite development path. PostgreSQL has no published port and capture mail ports remain loopback-only.

Before startup, keep APP_ORIGIN and ALLOWED_ORIGINS consistent with the actual browser origin/WEB_PORT. Local HTTP uses the development cookie setting; real HTTPS deployments require production mode and Secure cookies. The static server's no-referrer policy and access-log suppression protect reset query tokens. External reverse proxy and SMTP settings still require environment-specific configuration and verification.

Web and worker services restart unless stopped once explicitly selected. Repeated make targets reuse those service instances; do not run a separate native worker against the same workspace. No hourly integration or startup target deletes containers/volumes or silently changes cloud routing. Record image-build/Compose startup, migration, same-origin session/CSRF, financial-worker and SMTP outcomes against the final commit before labeling a container deployment verified. Current native routing and application tests do not establish container execution.

## Authorized Dokploy demo

Use the Git provider with the repository root as build context and Compose path `./compose.dokploy.yaml`. The separate deployment artifact activates web, API, one worker, migration, explicit idempotent demo bootstrap, PostgreSQL and private Mailpit without optional profiles or any host-published ports. Dokploy owns the project namespace. In Dokploy Domains, route `cadentra.midhunpm.in` with HTTPS to **web**, internal port **8080**, path `/`; do not create domains for API, database or capture. Only web joins the external dokploy-network; its NGINX reaches api:8001 on the private application network.

Supply APP_ORIGIN=https://cadentra.midhunpm.in and matching ALLOWED_ORIGINS in Dokploy's private Environment tab. The artifact enforces APP_ENV=production and Secure session cookies. Generate a URL-safe POSTGRES_PASSWORD and compliant DEMO_ADMIN_PASSWORD outside Git; provide DEMO_ADMIN_EMAIL privately. Bootstrap runs `python -m app.seed --demo` after migrations and before API/worker, retaining existing records/passwords on later runs. Demo credentials are passed only to bootstrap, never baked into images or source. SMTP defaults to the private capture service; provider credentials and settings remain environment-only. Private capture does not establish external delivery.

The equivalent host-side command is `docker compose --env-file <private-env-file> -f compose.dokploy.yaml up --build -d`; use Dokploy to perform the actual authorized deployment. Keep that file outside source and never print expanded Compose settings containing credentials. Build contexts resolve relative to this root Compose artifact. The [Dokploy Compose guide](https://docs.dokploy.com/docs/core/docker-compose/example) documents the Git source/Compose-path setup and domain configuration. Static validation is not proof of a deployed image, healthy service or working public HTTPS origin; record those results against the deployed commit separately.

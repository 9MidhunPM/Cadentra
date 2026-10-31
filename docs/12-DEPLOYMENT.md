# Deployment and runtime checklist

Proposed single-host deployment using Docker Compose, compatible with an existing reverse-proxy platform such as the user's Dokploy/Traefik environment. No server or domain has been changed by this pack. Do not modify live wildcard routing or other services without explicit approval.

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

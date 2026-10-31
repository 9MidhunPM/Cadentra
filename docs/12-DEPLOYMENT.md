# Current production email and homepage deployment

The existing Cadentra demo is hosted at https://cadentra.midhunpm.in. The cinematic release makes / public and /app the authenticated role landing; existing operational URLs are retained. HTTPS and exact proxy trust remain required.

Production now uses Resend SMTP instead of Mailpit. Configure these six values privately in Dokploy:

```text
COMPOSE_SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASSWORD=<private Resend API key>
SMTP_FROM=<address on your verified sending domain>
SMTP_STARTTLS=true
```

Never paste the key into Git or a frontend variable. The user has not yet configured SMTP_PASSWORD/SMTP_FROM. Empty values permit HTTP startup, but the transport rejects delivery before opening a connection, records SMTPNotConfigured and schedules a sanitized retry. There is no production Mailpit fallback. The old capture volume is retained. Development compose.yaml and .env.example are unchanged.

Both API and worker inherit the same backend environment; COMPOSE_SMTP_HOST maps to SMTP_HOST. APP_ORIGIN and ALLOWED_ORIGINS must be https://cadentra.midhunpm.in. Reset URLs are built from APP_ORIGIN and the dispatcher validates their origin/path. Port587 requires certificate-verified STARTTLS before authentication.

Private container check: `python -m app.smtp_check` validates configuration without connection or email; `python -m app.smtp_check --connect` verifies TLS/authentication without sending. Both return sanitized errors and nonzero status on failure. After configuration, verify a reset and invoice using an authorized controlled inbox; SMTP acceptance is separate from actual received mail.

Resend-Idempotency-Key, Message-ID, message date and MIME boundary remain stable for each persisted outbox intent. Provider deduplication lasts24hours; SMTP remains at-least-once across lost acknowledgement/database commit. Financial records are never recreated by email retries.

---

## Historical deployment preparation and ingress evidence

Statements below retain the facts and limitations of their original checkpoint. The production Mailpit defaults they describe are historical.

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

Use the Git provider with the repository root as build context and Compose path `./compose.dokploy.yaml`. The separate deployment artifact activates web, API, one worker, migration, explicit idempotent demo bootstrap, PostgreSQL and private Mailpit without optional profiles or any host-published ports. Dokploy owns the project namespace. In Dokploy Domains, route `cadentra.midhunpm.in` with HTTPS to **web**, internal port **8080**, path `/`; do not create domains for API, database or capture. Only web joins the external dokploy-network; its NGINX reaches api:8001 on the dedicated private proxy network.

Supply APP_ORIGIN=https://cadentra.midhunpm.in and matching ALLOWED_ORIGINS in Dokploy's private Environment tab. The artifact enforces APP_ENV=production and Secure session cookies. Generate a URL-safe POSTGRES_PASSWORD and compliant DEMO_ADMIN_PASSWORD outside Git; provide DEMO_ADMIN_EMAIL privately. Bootstrap runs `python -m app.seed --demo` after migrations and before API/worker, retaining existing records/passwords on later runs. Demo credentials are passed only to bootstrap, never baked into images or source. SMTP defaults to the private capture service; provider credentials and settings remain environment-only. Private capture does not establish external delivery.

The equivalent host-side command is `docker compose --env-file <private-env-file> -f compose.dokploy.yaml up --build -d`; use Dokploy to perform the actual authorized deployment. Keep that file outside source and never print expanded Compose settings containing credentials. Build contexts resolve relative to this root Compose artifact. The [Dokploy Compose guide](https://docs.dokploy.com/docs/core/docker-compose/example) documents the Git source/Compose-path setup and domain configuration. Static validation is not proof of a deployed image, healthy service or working public HTTPS origin; record those results against the deployed commit separately.

## Production client-address trust

The demo uses this explicit chain: Cloudflare → the existing Traefik container → Cadentra web → Cadentra API. Authentication limits must use the validated visitor address; using the web container address gives all visitors one shared login allowance. No application code trusts public `X-Forwarded-For` or `Forwarded` values.

The web service defines `cadentra-cloudflare-only`, an IPAllowList containing Cloudflare's published IPv4 and IPv6 ranges. **Attach `cadentra-cloudflare-only@docker` to the actual Cadentra domain in Dokploy Domains.** A middleware definition alone does not enforce anything. Keep the default RemoteAddr selection; do not configure an X-Forwarded-For depth or excluded-IP strategy. This checks the actual connecting edge peer and rejects direct-origin requests even if they forge Cloudflare headers. The Cadentra domain attachment has been saved and read back; runtime enforcement still requires public-origin and direct-origin checks. Other domains and global Traefik settings are outside this change.

Production web mode (`CADENTRA_TRUSTED_INGRESS=true`) must trust only the inspected static Traefik peer `10.0.1.20`, validate one `CF-Connecting-IP`, overwrite one `X-Cadentra-Client-IP` and remove competing forwarding headers before proxying. Revalidate that static address after infrastructure changes. The development NGINX configuration remains separate. Never broaden trust to every container/private subnet or enable Uvicorn wildcard forwarding trust.

The dedicated internal proxy network is `172.31.250.0/29`: web `.2`, API `.3`. The manifest declares web on that network and `dokploy-network`; the first actual Dokploy deployment also attached web to the application default network. The API also joins the application network for PostgreSQL/SMTP. Production NGINX must resolve `cadentra-api-proxy`, an alias defined only on the dedicated proxy network, so traffic still uses the exact `.2` → `.3` trust path. API production settings require exact `TRUSTED_WEB_PROXY_IPS` (`172.31.250.2` in the artifact), and Uvicorn runs with `--no-proxy-headers` so middleware sees the original socket peer. Missing, duplicate, malformed or noncanonical private headers and untrusted peers return a generic403. Only loopback GET/HEAD of the exact health endpoint bypass this proxy check for readiness. Origin, cookie and CSRF checks still apply to legitimate requests.

Check host subnet conflicts before rollout where host inspection is available. Docker must reject an overlapping allocation; never delete or alter another network to make this one fit. If an alternate subnet is needed, review all static addresses and exact trust settings together. Verify the deployed network memberships and API socket peer before accepting the release.

Regression coverage separates two clients behind one web peer, preserves the account-wide quota across clients, and rejects forged/duplicate/malformed headers. Deployment acceptance additionally requires real Cloudflare success, forged direct-origin rejection, private API exposure checks, health, login/logout and role/CSRF/ownership behavior. Run one API process; a shared quota store is required before horizontal scaling. Keep the official [Cloudflare IPv4](https://www.cloudflare.com/ips-v4) and [IPv6](https://www.cloudflare.com/ips-v6) ranges current through a reviewed change.


## First-container routing correction

The first actual Dokploy build/startup completed: migrations/bootstrap exited0, API/database/capture were healthy, and one worker plus UID101 web were running. Public HTTPS returned a Traefik404. Inspection showed the domain record persisted but no router/traefik.enable labels were injected alongside the custom middleware labels. Therefore the deployment artifact now defines explicit Cadentra-only HTTP/HTTPS routers and web:8080 service labels. Both routers require cadentra-cloudflare-only@docker; HTTP additionally uses its own HTTPS redirect. HTTPS uses the existing letsencrypt resolver. No wildcard/global router or other application's settings are modified. This uses the documented manual Compose routing method. The native domain entry remains a matching target record; inspect actual container labels after deployment.

Dokploy also attached web to the default application network. Do not broaden API proxy trust to compensate. The API's cadentra-api-proxy alias exists only on the dedicated proxy network, and the production frontend must use that alias. Verify actual DNS/source selection and successful public requests. The extra default attachment is an observed platform behavior, not proof of the stronger two-network-only manifest intent. Database/capture still publish no host ports or public routes, and web receives no database/admin credentials.

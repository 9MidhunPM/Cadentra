# Trusted-ingress native evidence

Base: `00ffa99`, isolated `feature/frontend-trusted-ingress` worktree. Native run: **26 checks passed**; all test listeners stopped. No database, real API, Cloudflare, Traefik or Docker execution occurred.

Exact command from the worktree root:

```sh
CADENTRA_TEST_NGINX=/tmp/cadentra-agent4-nginx-native/nginx-1.30.6/objs/nginx \
  python3 frontend/e2e/trusted-ingress.py
```

The NGINX 1.30.6 native binary was rebuilt from the previously signature-verified official source with `--with-http_realip_module`. Binary SHA256: `f6e74e621129abb4e0241e720c94b19b3087a83d147c605d3e1e6a0fea54472b`. Detailed cases, configuration hashes and adaptations are in [trusted-ingress-native.json](trusted-ingress-native.json). Shell syntax, Python compilation, Ruff F checks and diff checks also passed.

## Contract

`CADENTRA_TRUSTED_INGRESS=true` selects the separate production configuration. Compose must explicitly set this value; the coordinator confirmed that wiring. Unset or `false` selects the existing development configuration. Other values, including an explicitly empty value, exit64. The development `nginx.conf` remains byte-identical: SHA256 `96b4280b974063368fa06ef76b4caeee9d2ec7a8dfe6e2a2311bc3288325bb99`.

Production trusts only the original Traefik socket peer `10.0.1.20`. It reads `CF-Connecting-IP`, rejects missing, malformed, comma-separated or duplicate values and requires a successful changed-address rewrite. IPv4 shape checks reject invalid octets and leading zeros; NGINX realip parses the complete IPv4/IPv6 address. Wrong peers and no-rewrite identities return403 before upstream access.

The proxy overwrites incoming internal identity fields with exactly one `X-Cadentra-Client-IP: $remote_addr`, and removes `X-Forwarded-For`, `Forwarded`, `X-Real-IP` and `CF-Connecting-IP`. Native raw HTTP checks transmitted duplicate headers separately, including mixed-case names. Expanded IPv6 normalized to `2001:db8::1`; spoofed internal duplicates were overwritten once. Origin, Cookie, CSRF, Host, request body/query, upstream404, response cookies, DNS configuration, SPA fallback, asset cache/gzip and HTML referrer policy remain intact.

The entrypoint writes generated PID/config/temp paths only under `/tmp/cadentra-nginx`, leaving `/etc` untouched. Native selector checks ran nonroot with source files0444 and their directory0555. This simulates immutable configuration, not an actual read-only container root filesystem.

There is **no HTTP healthcheck bypass**. Direct loopback HTTP without the trusted identity returns403. Production health must follow the coordinator's local configuration/process contract; its generated configuration is `/tmp/cadentra-nginx/nginx.conf`.

## Adaptations and limits

The native policy replaced the exact trusted peer with `127.0.0.1` only; `127.0.0.2` was the rejected peer. Listener, static/MIME/runtime paths and API/DNS fixture destinations were task-owned loopback/temp resources. Test HTML/API payloads are explicitly protocol fixtures, not application success evidence.

Docker build/entrypoint execution, actual Traefik/Cloudflare filtering, production networking, the API's exact `172.31.250.2` web-peer trust and disabled Uvicorn proxy-header wiring remain separate integration checks. The topology depends on Traefik's application-only allowlist checking its original `RemoteAddr` against official Cloudflare ranges.

## Official sources

- [NGINX realip directives, original-peer variable and build flag](https://nginx.org/en/docs/http/ngx_http_realip_module.html).
- [NGINX proxy header replacement/removal](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header).
- [NGINX-maintained unprivileged image source](https://github.com/nginx/docker-nginx-unprivileged/blob/main/stable/alpine-slim/Dockerfile): NGINX1.30.6-r1 package installation and nonroot runtime.
- [Versioned official Alpine packaging source](https://github.com/nginx/pkg-oss/blob/1.30.6-1/alpine/Makefile): `BASE_CONFIGURE_ARGS` includes `--with-http_realip_module`.
- [Cloudflare's CF-Connecting-IP contract](https://developers.cloudflare.com/fundamentals/reference/http-headers/#cf-connecting-ip).

The official image/package sources support expected module availability; the pinned container image itself was not executed.

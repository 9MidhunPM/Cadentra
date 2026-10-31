# Browser and performance checks

Run these commands from `frontend/`. They have different data and runtime requirements.

| Check | Command | Scope |
| --- | --- | --- |
| Component tests | `npm test` | Vitest under `src/`; no real HTTP/database claim. |
| Transport regression | `node --experimental-strip-types --test e2e/performance-response.test.ts` | Seven Node tests for benchmark response completion, including anonymous session 401 cancellation. This is separate from Vitest and Playwright. |
| Fixture UI | `npx playwright test --config playwright.config.ts` | Only `*.spec.ts`; explicitly mocked feature/session data. Vite starts on 5174. Workspace tests enter `/app`; `/` is the public homepage. |
| Real reports/portal | `npx playwright test --config playwright.live.config.ts` | Requires the private `CADENTRA_LIVE_CREDENTIALS` small-fixture manifest and a separately started fixed-clock test API on 8004. Vite uses 5174. Invoice ownership/printing is mandatory, not opt-in. |
| Complete journey | `npx playwright test --config playwright.journey.config.ts` | Requires its private journey manifest and separately prepared API/data. Performs real financial and lifecycle mutations; follow the coordinator-approved isolated-fixture procedure. |
| Final native timing | `npx playwright test --config playwright.performance.config.ts` | Requires a frozen reviewed source, private T30 manifest, fresh API and separately started native NGINX on 8080 serving its recorded production build. No Vite or protocol mocks. Required run/artifact/server-metadata environment variables are validated by the configuration. |

`npx playwright test --config playwright.config.ts --list` validates fixture discovery without launching its browser/server. The Node transport file must not appear in that list. Ordinary `npm test`/`make test` does not run the explicit browser suites or the Node transport checks.

Use the installed pinned Chromium with `PLAYWRIGHT_BROWSERS_PATH=/tmp/cadentra-agent4-browsers` in this workspace. This is native local evidence, separate from the coordinator's real public deployment checks.

The old `cadentra_experience_test` retains immutable T31 history. Do not seed, rerun broad database suites, bypass guards or attempt cleanup there. The private T30 dataset is separately bound to its generated UUID namespace in `cadentra_performance_test`. Never use its manifest for the small live/journey suites. Fresh live/journey runs require a separately approved empty fixture target; these commands are not permission to reuse retained history.

Keep manifests/passwords/session cookies under private mode 0600 `/tmp` files and out of commits. Stop the exact owned browser/API/server processes before any approved guarded fixture teardown. Final timing remains incomplete until the complete current matrix and capture pass; historical partial measurements do not establish the every-page target.

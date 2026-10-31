# Release evidence

Status: SHARED FOUNDATION GATE A VERIFIED LOCALLY. FULL PRODUCT IMPLEMENTATION CONTINUES.

## Event and publishing
Approved repository/name: Cadentra; 9MidhunPM/Cadentra (user confirmed)
User-selected publishing workflow: one-time planning-pack main initialization, then feature branches and PRs
Organiser clarification for PR workflow: NOT VERIFIED
Repository submission confirmation: NOT RECORDED
Evaluator access: NOT VERIFIED
Tool-use permission under event rules: NOT VERIFIED
Contributor ownership: Midhun P M, Thanushree Suresh, Noel Biju and Sherin Saji
Actual application contributions: reviewed feature PRs and handoffs record the first backend, frontend, calendar and pricing slices

## Candidate
Backend implementation: f6f3f79a024cd4da1bc049f8aecb0d1c68ac9df5
Integrated release commit: record exact main merge after PR4
Migration revision:0002
Dependency versions: backend/uv.lock and frontend/package-lock.json
Deployment: NOT CREATED

## Checks actually executed against the app
Backend tests:74PASS in the unified suite against real PostgreSQL18.6 (includes pure calendar/pricing checks)
Concurrency tests: NOT RUN
Frontend type/lint/build: PASS;47unit/component tests PASS
Browser full workflow: NOT RUN
Customer isolation: foundation role/session restrictions verified; cross-customer subscription/invoice workflows await domain services
Real reset/invoice email delivery: NOT RUN
Performance benchmark: NOT RUN
Fresh-clone reproduction: NOT RUN

## Known gaps
Identity/customer/catalog backend APIs and shared foundation are implemented and locally verified. Full subscription/billing/reporting/portal workflows, remaining subscription/billing/reporting screens, performance and external delivery remain in progress. Identity/catalog screens are now verified in real browser/API flows; payment concurrency is verified in the independently reviewed billing API slice.

## Gate A local browser evidence

Real Chromium through the Vite proxy and PostgreSQL-backed API passed: health200, signup201, login/session200, role403, missing-CSRF403, customer navigation, logout200 and subsequent401; zero page errors. Script: scripts/check_gate_a.mjs. Local screenshot inspected. Initial frontend fixture tests are separate evidence and do not prove backend authentication.

## Active integration cadence

User requested hourly integration. Contributors were notified through Codex TUI and assigned independent native test databases. Coordinator reviews/merges ready PRs serially, earlier than the hourly checkpoint when useful. No failing work is merged for time alone.

## Demo/submission
Video: NOT RECORDED
Signed-out access: NOT CHECKED
Final portal confirmation: NOT RECORDED

## Subsequent integration evidence

Identity/catalog experience:91frontend tests, type/lint/build and real Chromium admin/customer/staff persistence/restriction flows pass. Native full suite before billing API integration:104backend tests pass. Local password-reset UI/outbox/SMTP/Mailpit/new-password sign-in passes with fictional data. Mailpit is checksum-verified native1.33.0; Compose service is pinned but Docker execution remains untested. External email is not configured or attempted.

Billing API PR7 has independent48tests including3true PostgreSQL payment/cancellation races. Portal integration subsequently identified a nested invoice-metadata privacy regression; the billing owner is patching it before customer-safe portal release. Do not mark that integration complete until its regression passes.

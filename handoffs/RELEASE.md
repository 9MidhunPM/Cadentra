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
Backend tests:61PASS plus80subtests against real PostgreSQL18.6 before pricing integration
Concurrency tests: NOT RUN
Frontend type/lint/build: PASS;47unit/component tests PASS
Browser full workflow: NOT RUN
Customer isolation: foundation role/session restrictions verified; cross-customer subscription/invoice workflows await domain services
Real reset/invoice email delivery: NOT RUN
Performance benchmark: NOT RUN
Fresh-clone reproduction: NOT RUN

## Known gaps
Identity/customer/catalog backend APIs and shared foundation are implemented and locally verified. Full subscription/billing/reporting/portal workflows, identity/catalog business screens, true financial concurrency, performance and external delivery remain in progress.

## Gate A local browser evidence

Real Chromium through the Vite proxy and PostgreSQL-backed API passed: health200, signup201, login/session200, role403, missing-CSRF403, customer navigation, logout200 and subsequent401; zero page errors. Script: scripts/check_gate_a.mjs. Local screenshot inspected. Initial frontend fixture tests are separate evidence and do not prove backend authentication.

## Active integration cadence

User requested hourly integration. Contributors were notified through Codex TUI and assigned independent native test databases. Coordinator reviews/merges ready PRs serially, earlier than the hourly checkpoint when useful. No failing work is merged for time alone.

## Demo/submission
Video: NOT RECORDED
Signed-out access: NOT CHECKED
Final portal confirmation: NOT RECORDED

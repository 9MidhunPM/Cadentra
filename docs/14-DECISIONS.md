# Decision and risk register

User decisions below were accepted during planning on 31 October 2026 (Asia/Kolkata). User acceptance settles the implementation baseline; it does not establish organiser approval or completed implementation. Midhun P M coordinates changes and records supporting evidence.

| ID | Decision / assumption | Current status | Owner |
|---|---|---|---|
| D01 | Product name Cadentra; challenge remains Subscription Management System | Accepted project baseline; name/trademark availability unchecked | Midhun P M |
| D02 | React/Vite + FastAPI + PostgreSQL with shared backend business logic | USER ACCEPTED; pin compatible versions at bootstrap | Midhun P M + Sherin Saji |
| D03 | Four named contributors, independent clones, accurate participant attribution | USER ACCEPTED; participant accounts/keys/access remain unverified | Midhun P M |
| D04 | Feature-named branches and PRs to main; one initial planning-pack push establishes main | USER APPROVED; organiser single-branch interpretation remains unverified | Midhun P M |
| D05 | Assistant/tool use under event rules | UNVERIFIED from reviewed written rules; no permission claim inferred from team naming | Midhun P M |
| D06 | Plan base fee plus product lines; one currency INR | USER ACCEPTED engineering baseline | Midhun P M + Noel Biju |
| D07 | Bill in advance, anchored dates, no proration/refunds | USER ACCEPTED; disclose full-cycle policy | Midhun P M + Thanushree Suresh + Noel Biju |
| D08 | Pause/close at next boundary; renewal creates linked draft | USER ACCEPTED | Midhun P M + Thanushree Suresh |
| D09 | One best discount; global cap consumed at draft; cancellation does not restore use | USER ACCEPTED | Midhun P M + Noel Biju |
| D10 | Taxes after discounts, line-level rounding, non-compounding | USER ACCEPTED illustrative policy; no tax-law compliance claim | Midhun P M + Noel Biju |
| D11 | Real SMTP provider and deployment origin | Not configured | Midhun P M |
| D12 | Dependency/runtime/container versions | Not resolved; record locked versions below | Midhun P M + Sherin Saji |
| D13 | Every page under 2s with thousands of subscriptions | Source requirement; NOT MEASURED | Sherin Saji |
| D14 | Eight-hour target | Aggressive target, not guarantee | All four contributors |
| D15 | Midhun P M owns coordination and Platform & Catalog; Thanushree Suresh subscriptions; Noel Biju billing; Sherin Saji experience/reporting | USER ASSIGNED; people own workstreams and assistants follow their role instructions | Midhun P M |

## Accepted user decisions: 31 October 2026 (Asia/Kolkata)

Source: the user's interactive planning answers and subsequent instruction to implement the plan. Exact clock time was not recorded.

- Selected Midhun P M's delivery plan after naming cleanup and assigned coordination to Midhun P M.
- Accepted the existing stack, API/data/domain baseline and documented billing policies.
- Required feature names for branches without personal names. Each teammate's assistant creates its branch and opens a PR when ready, or asks Midhun P M to create the prepared PR.
- Explicitly selected one initial planning-pack push to main because the remote had no branches. Subsequent application work uses feature branches and PRs.
- Requested notification once the first commit and teammate startup documentation are ready. Documentation readiness does not mark Gate A or application requirements complete.

Affected areas: shared and role instructions, launch prompts, handoffs, Git/integration/execution documentation and pack validation. Naming changes leave API wire shapes and financial fixtures unchanged. Application migrations and dependency locks are still pending.

## Risks and mitigations

**R1: Shared schema becomes a bottleneck.** Freeze table/field contracts early; one migration owner; additive change requests.
**R2: Shared frontend workload.** Midhun P M/Thanushree Suresh/Noel Biju own UI for their features; Sherin Saji owns common shell, reporting and portal.
**R3: Billing races or rounding drift.** Decimal fixtures, real PostgreSQL concurrent tests, unique period keys, immutable snapshots.
**R4: Missing delivery credentials.** Configure SMTP at the start, not at recording time. A captured email is not delivered email.
**R5: Scope too large.** Establish the vertical slice early; cut optional features first; list required gaps honestly.
**R6: Wrong GitHub account pushes.** Verify the authorized account for the configured HTTPS/SSH transport, local author identity and environment overrides before publishing.
**R7: Event branch/contribution ambiguity.** The user selected PRs; Midhun P M separately records organiser clarification without committing private correspondence or claiming unverified compliance.
**R8: Reporting overclaims.** Separate cash, invoiced amount and outstanding; no unimplemented bank reconciliation, MRR or legal compliance claims.
**R9: Demo clock escapes into deployment.** Inject clock only in tests/explicit demo mode; no public arbitrary as_of endpoint.
**R10: Public demo mutation.** Use disposable fictional data, no production secrets; decide who receives staff/admin access.

## Decision log template

Date/time (with timezone):
Decision ID:
Decision:
Source or rationale:
Approved by:
Affected files/contracts:
Migration/test impact:

## Resolved versions

Python: 3.12.13
Node: verified 26.12.1, frontend minimum >=22.12
PostgreSQL: 18.6 (native signed Arch runtime verified; Compose image pinned 18.6-bookworm)
Backend lockfile: backend/uv.lock; FastAPI 0.162.0, SQLAlchemy 2.0.55, Alembic 1.20.1, psycopg 3.3.6; all transitives locked
Frontend lockfile: frontend/package-lock.json from Sherin Saji foundation; React 19.3.1, React Router 8.5.1, Vite 8.3.5, TypeScript 6.0.3
Container tags/digests: python:3.12.13-slim-bookworm, postgres:18.6-bookworm, uv:0.12.9; container execution remains untested in this shell

## Foundation coordination decisions

2026-10-31: coordinator confirmed typed session/actor/clock/money imports, immutable cycle/pricing DTO boundaries, template/edit/date rules, stable tax/discount identities with retained revisions, issue-date catch-up billing and serial hourly PR integration. See API/domain/data-model documents for exact contracts. Other feature owners retain implementation ownership. Native PostgreSQL test verification is distinct from unperformed Docker/deployment/email tests.

2026-10-31 user clarification: participants remain SSH-key-only and do not log into gh. Coordinator creates/reviews/merges prepared PRs with the existing 9MidhunPM API account; do not claim that PR author is the SSH account. Original participant commit metadata is preserved. All three workstreams received this correction through Codex TUI.

Experience update: Sherin Saji's user-selected Graphite Mint default dark / Sage Commerce light baseline is integrated through PR5, with shared semantic tokens and accessible motion/navigation. Root identity/catalog screens use these exports.

# Cadentra: start here

**Every subscription. Every cycle. Accounted for.**

Cadentra is the four-person team's application for the **Subscription Management System** challenge. Brightloop Software remains the fictional business in the supplied brief. Product/domain/trademark availability has not been checked.

## Current checkpoint

**Gate A passed locally.** Reviewed main now includes persistent identity/catalog, subscription workflows, recurring billing, payment/rule APIs, reports and owned portal reads. Final UI, delegated portal actions and end-to-end acceptance work continues; read [release evidence](handoffs/RELEASE.md) for exact tested commits and limits. Midhun P M owns shared backend infrastructure and coordination. The approved remote is https://github.com/9MidhunPM/Cadentra. The current delivery workflow is exact code/test review by Midhun P M, followed by each owner's local reviewed merge and normal SSH push to main in a serialized turn. Earlier PRs remain historical records; new PRs are not required.

## Team and startup prompts

| Contributor | Responsibility | Role file | Prompt | Historical initial branch |
|---|---|---|---|---|
| Midhun P M | Coordination, Platform & Catalog | `team/midhun-p-m/AGENTS.md` | `prompts/01-PLATFORM.md` (bootstrap prompt is historical) | `feature/platform-foundation` |
| Thanushree Suresh | Subscription Workflows | `team/thanushree-suresh/AGENTS.md` | `prompts/02-SUBSCRIPTIONS.md` | `feature/subscription-workflows` |
| Noel Biju | Billing & Payments | `team/noel-biju/AGENTS.md` | `prompts/03-BILLING.md` | `feature/billing-payments` |
| Sherin Saji | Experience & Reporting | `team/sherin-saji/AGENTS.md` | `prompts/04-EXPERIENCE.md` | `feature/frontend-foundation` |

There are four human owners. Each person's assistant works on that person's assigned workstream. Coordinator duties belong to Midhun P M rather than a fifth participant.

## Start in this order

1. Read root `AGENTS.md`, your named role file above, `docs/01-MVP.md`, and `docs/08-EXECUTION-PLAN.md`. Each startup prompt explicitly loads its role file; nested instruction files are not automatically discovered from a root session.
2. Use your own independent clone. Inspect existing local work and preserve it. Fetch `origin`, then create a descriptive feature branch from reviewed `origin/main` for the next slice. The table lists the historical initial branches; preserve them. If the branch already exists, inspect it and continue safely. Keep branch names about features, not people.
3. Run `python3 scripts/check_pack.py` and `bash scripts/preflight.sh`. These verify the planning assets and local setup; they do not prove account authentication or application correctness. Follow `docs/13-GIT-IDENTITIES.md` for participant-controlled authentication.
4. **Historical foundation ownership (already integrated):** Midhun P M supplied the backend/models/migration/helpers/stubs; Sherin Saji supplied the frontend shell, reusable primitives, transport and feature placeholders. Continue feature work against that shared baseline and current handoffs. Do not reinitialize the application or create a competing migration history.
5. **Gate A was verified:** The backend and frontend foundation changes were integrated and verified. Existing PR records describe the historical process. The database migration applies; API and frontend boot; all agreed module placeholders import; API/auth/error/money shapes and shared frontend exports are agreed. Domain implementation starts from this integrated baseline.
6. Deliver a small working slice within your owned paths. Run actual tests; review the diff; update your named handoff with the exact implementation commit, results, blockers and shared change requests.
7. Send the exact ready feature head, expected main SHA, changed paths, test results and dependencies to Midhun P M through Codex TUI. Midhun P M reviews that code and evidence, then gives GO for one owner to publish at a time. Incomplete or failing slices wait; hourly checkpoints do not bypass review.
8. After GO, the owner fetches/rechecks main against the approved SHA, performs the reviewed local merge in a clean checkout, reruns affected checks and pushes main normally using their own verified SSH identity. If remote main changes, conflicts change the result, or a push is rejected, stop and refetch/review before another attempt. Never force, delete, rewrite shared history or push an unreviewed slice.
9. Report the resulting main SHA and results so Midhun P M can release the next turn. Midhun P M reviews code/tests and coordinates turns; there is no current coordinator gh/API PR-creation/merge step. Midhun P M's existing default SSH identity is verified as 9MidhunPM; other owners retain their assigned keys. Preserve global Git/SSH/auth settings. See `docs/09-INTEGRATION.md` and `docs/13-GIT-IDENTITIES.md`.

Midhun P M owns the user-authorized Dokploy subdomain demo deployment. Record the actual deployed commit, origin and smoke results in release evidence; local Gate A verification does not establish deployment success.

## First product milestone

`Product + variant + plan -> quotation -> confirmed subscription -> active subscription -> recurring invoice -> payment -> dashboard + customer portal`

Complete this persisted, permission-checked journey first. Optional **CycleGuard** must read real billing records and follows required functionality.

## Timeline and evidence

The eight-hour schedule is an aggressive target relative to the actual permitted coding start; the portal timeline takes precedence. Aim for the paid-invoice journey by hour 4; prioritize required coverage and fixes after hour 6. Keep required gaps explicit.

The user selected owner-operated local merges and normal SSH pushes to main after exact review and serialized GO. The historical event sources still contain a single-branch ambiguity and do not establish unrestricted assistant-use permission; Midhun P M records any organiser clarification separately. Choosing the team's workflow does not verify portal submission, hourly participation, account ownership or deployment.

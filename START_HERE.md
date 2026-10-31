# Cadentra: start here

**Every subscription. Every cycle. Accounted for.**

Cadentra is the four-person team's application for the **Subscription Management System** challenge. Brightloop Software remains the fictional business in the supplied brief. Product/domain/trademark availability has not been checked.

## Current checkpoint

**Gate A passed locally.** Reviewed main now includes persistent identity/catalog, subscription workflows, recurring billing, payment/rule APIs, reports and owned portal reads. Final UI, delegated portal actions and end-to-end acceptance work continues; read [release evidence](handoffs/RELEASE.md) for exact tested commits and limits. Midhun P M owns shared backend infrastructure and coordination. The approved remote is https://github.com/9MidhunPM/Cadentra. The user authorized one initial planning-pack commit/push to `main`; subsequent application changes use feature branches and PRs.

## Team and startup prompts

| Contributor | Responsibility | Role file | Prompt | Starting feature branch |
|---|---|---|---|---|
| Midhun P M | Coordination, Platform & Catalog | `team/midhun-p-m/AGENTS.md` | `prompts/00-BOOTSTRAP.md`, then `prompts/01-PLATFORM.md` | `feature/platform-foundation` |
| Thanushree Suresh | Subscription Workflows | `team/thanushree-suresh/AGENTS.md` | `prompts/02-SUBSCRIPTIONS.md` | `feature/subscription-workflows` |
| Noel Biju | Billing & Payments | `team/noel-biju/AGENTS.md` | `prompts/03-BILLING.md` | `feature/billing-payments` |
| Sherin Saji | Experience & Reporting | `team/sherin-saji/AGENTS.md` | `prompts/04-EXPERIENCE.md` | `feature/frontend-foundation` |

There are four human owners. Each person's assistant works on that person's assigned workstream. Coordinator duties belong to Midhun P M rather than a fifth participant.

## Start in this order

1. Read root `AGENTS.md`, your named role file above, `docs/01-MVP.md`, and `docs/08-EXECUTION-PLAN.md`. Each startup prompt explicitly loads its role file; nested instruction files are not automatically discovered from a root session.
2. Use your own independent clone. Inspect existing local work and preserve it. Fetch `origin`, then create a descriptive feature branch from reviewed `origin/main` for the next slice. The table lists the historical initial branches; preserve them. If the branch already exists, inspect it and continue safely. Keep branch names about features, not people.
3. Run `python3 scripts/check_pack.py` and `bash scripts/preflight.sh`. These verify the planning assets and local setup; they do not prove account authentication or application correctness. Follow `docs/13-GIT-IDENTITIES.md` for participant-controlled authentication.
4. **Historical foundation ownership (already integrated):** Midhun P M builds the shared backend/models/migration/helpers/stubs on `feature/platform-foundation`. Sherin Saji can start the frontend shell, reusable primitives, transport and feature placeholders on `feature/frontend-foundation`. Thanushree Suresh and Noel Biju can review contracts, prepare domain test cases and record interface requests in their handoffs. Do not reinitialize the application or create a competing migration history.
5. **Gate A was verified:** Midhun P M integrated the backend and frontend foundation PRs. The database migration applies; API and frontend boot; all agreed module placeholders import; API/auth/error/money shapes and shared frontend exports are agreed. Domain implementation starts from this integrated baseline.
6. Deliver a small working slice within your owned paths. Run actual tests; review the diff; update your named handoff with the exact implementation commit, results, blockers and shared change requests.
7. Push your tested feature branch using your verified owner SSH key. Send the exact head, title/body, checks and comparison link through Codex TUI; Midhun P M creates/reviews/merges the PR with existing coordinator API authentication. Do not initiate participant gh/OAuth/token login. See `docs/09-INTEGRATION.md`. All subsequent application changes go through this workflow.
8. Midhun P M coordinates review and integration; each contributor then brings the reviewed baseline into their own branch without rewriting shared history.

## First product milestone

`Product + variant + plan -> quotation -> confirmed subscription -> active subscription -> recurring invoice -> payment -> dashboard + customer portal`

Complete this persisted, permission-checked journey first. Optional **CycleGuard** must read real billing records and follows required functionality.

## Timeline and evidence

The eight-hour schedule is an aggressive target relative to the actual permitted coding start; the portal timeline takes precedence. Aim for the paid-invoice journey by hour 4; prioritize required coverage and fixes after hour 6. Keep required gaps explicit.

The team has selected feature branches and PRs. The historical event sources still contain a single-branch ambiguity and do not establish unrestricted assistant-use permission; Midhun P M records any organiser clarification separately. Choosing the team's workflow does not verify portal submission, hourly participation, account ownership or deployment.

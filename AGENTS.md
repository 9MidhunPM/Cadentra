# Cadentra: shared contributor instructions

## Purpose and authority
Build the Subscription Management System described in `references/Subscription_Management_System.pdf`.
Cadentra is the approved project name. Read `docs/00-SOURCES.md` before treating a design choice as an organiser rule.
The initial commit established the planning pack. Current implementation and integrated Gate A evidence are recorded in handoffs/RELEASE.md; never infer readiness from a scaffold alone.

## Required reading
Read `START_HERE.md`, your explicitly assigned `team/*/AGENTS.md`, `docs/05-API-CONTRACT.md`, and the relevant sections of `docs/06-DOMAIN-RULES.md`.
An assistant works on behalf of the named contributor; the role does not authorize impersonation or invented contributions.
Work within that contributor's scope. If no role has been assigned, identify the missing assignment before editing.

## Architecture
One React/Vite client, one FastAPI backend, one PostgreSQL database per workspace, one standalone worker process.
Business logic belongs on the backend. The frontend must not invent invoice totals or authorization.
The stack and documented domain policies are approved. Midhun P M and Sherin Saji resolve and lock compatible dependencies during foundation work; subsequent work uses that baseline.

## Ownership
Midhun P M coordinates decisions, contract changes, exact code/test review and serialized integration clearance. Midhun P M owns all database models, migrations, backend wiring, environment contracts and backend dependency manifests, plus identity/catalog features.
Sherin Saji owns frontend routing, shared UI, styles, API transport, frontend dependency manifests and browser-test configuration, plus reporting/portal features.
Thanushree Suresh owns subscription feature directories and tests, including their feature UI. Noel Biju owns billing feature directories and tests, including their feature UI.
Shared changes require a decision from Midhun P M and a request in the requesting contributor's named handoff file.
Only Midhun P M edits frozen contract documents after Gate A.

## Startup and Git workflow
Use your assigned independent clone. Inspect its status, branch, remote and effective author identity first; preserve unrelated local work.
Fetch `origin`, then create a descriptive feature branch from reviewed `origin/main` for the next slice. Historical foundation branches already exist; inspect their ancestry rather than recreate or overwrite them. Use feature names without participant names.
The current user-selected delivery workflow is owner-operated local integration and normal SSH push to main after exact review. Earlier planning-pack/PR procedures are history; there is no current PR requirement.

1. Prepare a scoped feature commit, run applicable checks and update your handoff with exact head, changed paths, commands/results, gaps and dependencies. Send the ready head and expected main SHA to Midhun P M through Codex TUI.
2. Midhun P M reviews the exact code and test evidence, then gives GO for that feature head and expected main SHA. Midhun P M serializes one main push at a time; each contributor waits for their turn. An elapsed checkpoint is not clearance.
3. The owning contributor fetches/rechecks remote main before integration. If main differs from the approved SHA, stop, refetch and obtain renewed review/GO against the new main. Do not publish a stale approval.
4. In the owner's clean checkout, merge only the reviewed slice locally into main while preserving commit authorship and shared history. If conflicts or other changes alter the reviewed result, resolve in scope, rerun affected checks and return the exact candidate for review before publishing.
5. Recheck the expected remote main immediately before the normal SSH push. The owner pushes main using their own verified SSH identity; a race/rejection requires stopping, refetching and renewed review. Never force-push, delete branches, rewrite history or publish an unreviewed slice.
6. Report the resulting main SHA and executed checks to Midhun P M, who releases the next integration turn. Bring reviewed main into ongoing feature work without rewriting shared history.

Midhun P M reviews code/tests and coordinates turns; the coordinator does not create or merge PRs through gh/API on behalf of contributors. Use the contributor's verified SSH identity for Git operations. Midhun P M's existing default SSH identity is verified as 9MidhunPM; preserve it. Other contributors use their existing assigned owner keys as documented in docs/13-GIT-IDENTITIES.md.
Do not initiate gh login, OAuth, token setup, account switching or global Git/SSH/auth configuration changes.
The user requests hourly integration checkpoints during active work. Keep tested slices ready and report exact heads/checks/dependencies; incomplete or failing slices are not published merely to meet the clock.
The user selected this workflow. Organiser compatibility remains unverified; record clarification separately rather than claim it was obtained.

## Credentials and destructive actions
Do not create a remote repository, register keys or modify global Git, SSH or GitHub CLI configuration.
Do not read, print, copy or upload private keys, .env secrets or authentication tokens.
Use authorized credentials and accurate participant attribution. Never manufacture contribution activity.
Never force-push, delete work, reset --hard, clean -fd, drop databases or remove volumes without explicit human approval.
Do not disable approvals or broaden tool permissions.

## Non-negotiable domain rules
Preserve Draft -> Quotation -> Confirmed -> Active -> Closed.
Use Decimal/database NUMERIC for financial arithmetic, and decimal strings in JSON.
Store immutable invoice snapshots; never recompute old invoice totals from current catalog data.
Billing retries must not create duplicate subscription-period invoices.
Enforce permissions and customer ownership on every backend read and write, not just in navigation.
Use real persistent data. Mark development mocks explicitly and remove them from the submission.
Do not change dates, currency, rounding, lifecycle or discount semantics without a recorded decision.

## Delivery and coordination
Gate A has passed locally: the backend/frontend foundations are integrated and verified. Continue from the existing application and current release evidence; do not reinitialize scaffolds or create competing migration histories. Check latest handoffs for the exact tested commits and remaining gaps.
Deliver small working slices with tests. Validate boundary inputs and relevant database constraints.
No catch-all exception swallowing, fake success responses, hard-coded dashboard totals or inert buttons.
Use request-scoped database sessions and explicit transactions for financial operations. Handle loading, empty, error and forbidden UI states.
Update only your named handoff in `handoffs/`; include exact implemented commit, files, tests actually run, blockers and integration needs. The coordinator may update release evidence and maintain the planning pack.
Never mark an unrun test as passing. Never claim email delivery when only queued or captured locally.
Midhun P M owns deployment and the user-authorized Dokploy subdomain demo. Coordinate deployment changes through that owner and record actual runtime evidence.
The four contributor workstreams define ownership. If blocked, prepare scoped tests or a compatible adapter rather than fork shared contracts.
Before handoff, inspect the diff for secrets and out-of-scope edits. After hour 6, prioritize integration and correctness over optional features.

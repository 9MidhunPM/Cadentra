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
Midhun P M coordinates decisions, contract changes, PR review and integration. Midhun P M owns all database models, migrations, backend wiring, environment contracts and backend dependency manifests, plus identity/catalog features.
Sherin Saji owns frontend routing, shared UI, styles, API transport, frontend dependency manifests and browser-test configuration, plus reporting/portal features.
Thanushree Suresh owns subscription feature directories and tests, including their feature UI. Noel Biju owns billing feature directories and tests, including their feature UI.
Shared changes require a decision from Midhun P M and a request in the requesting contributor's named handoff file.
Only Midhun P M edits frozen contract documents after Gate A.

## Startup and Git workflow
Use your assigned independent clone. Inspect its status, branch, remote and effective author identity first; preserve unrelated local work.
Fetch `origin`, then create your role's feature branch from reviewed `origin/main` in a clean checkout. If that branch already exists, inspect its ancestry and continue safely rather than overwrite it. Never reset another person's work.
Use feature names in branches, without participant names. Role files specify the initial branch; subsequent slices use a new descriptive `feature/<functionality>` branch after the previous PR is integrated.
The user authorized a one-time initial planning-pack commit/push to establish `main`. All subsequent application work goes through feature branches and PRs targeting `main`; do not push application changes directly to `main`.
After tests and handoff review, participants push feature branches with their verified owner SSH keys. The user selected SSH-only participant workspaces: do not initiate gh login, OAuth, token setup or account switching. Send the exact ready head, title, description, validation results and comparison link to Midhun P M through Codex TUI. The coordinator creates/reviews/merges PRs with the existing authorized 9MidhunPM API account; preserve original commit authorship and report PR authorship accurately.
PRs record delivered behavior, exact checks, known gaps, dependencies and shared-change requests. Midhun P M reviews and integrates small slices, preserving accurate contribution history.
The user requests hourly integration checkpoints during active work. Keep tested feature slices ready, report exact heads/checks/dependencies, and incorporate reviewed main into feature branches at least hourly. Midhun P M serializes reviewed PR merges; incomplete or failing slices are not merged merely to meet the clock.
The user selected this PR workflow. Organiser compatibility remains unverified; record later clarification without presenting it as already obtained.

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
Before Gate A, Midhun P M builds the backend foundation and Sherin Saji builds the frontend foundation. Thanushree Suresh and Noel Biju review contracts and prepare scoped tests; they do not initialize competing applications.
Gate A passes only after both foundations are integrated, models/migration and module imports work, frontend/API boot together, and shared interfaces are agreed. Check the latest handoffs before starting dependent implementation.
Deliver small working slices with tests. Validate boundary inputs and relevant database constraints.
No catch-all exception swallowing, fake success responses, hard-coded dashboard totals or inert buttons.
Use request-scoped database sessions and explicit transactions for financial operations. Handle loading, empty, error and forbidden UI states.
Update only your named handoff in `handoffs/`; include exact implemented commit, files, tests actually run, blockers and integration needs. The coordinator may update release evidence and maintain the planning pack.
Never mark an unrun test as passing. Never claim email delivery when only queued or captured locally.
The four contributor workstreams define ownership. If blocked, prepare scoped tests or a compatible adapter rather than fork shared contracts.
Before handoff, inspect the diff for secrets and out-of-scope edits. After hour 6, prioritize integration and correctness over optional features.

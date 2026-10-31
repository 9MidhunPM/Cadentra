# Integration, event constraints and collaboration

## Selected team workflow

Midhun P M coordinates the four-person team and owns integration. The user approved independent clones, feature-named branches and PRs targeting main on 31 October 2026 (Asia/Kolkata). The single initial planning-pack commit/push establishes main for PRs. After that bootstrap, application changes go through feature branches and PR review.

| Person | Initial branch | Start work |
|---|---|---|
| Midhun P M | feature/platform-foundation | Shared backend/models/migration and runtime baseline |
| Thanushree Suresh | feature/subscription-workflows | Contract review and lifecycle tests; domain implementation after Gate A |
| Noel Biju | feature/billing-payments | Billing vectors and contract tests; domain implementation after Gate A |
| Sherin Saji | feature/frontend-foundation | Shared frontend shell, primitives, API/session client and placeholders |

Later branches use feature names such as feature/authentication, feature/catalog and feature/reporting-portal. Branch names contain neither participant names nor numbered role labels. One branch delivers one reviewable feature slice.

## Starting and delivering a slice

1. Read root AGENTS.md, START_HERE.md and the explicitly assigned team role file in your own independent clone. Inspect Git status, current branch, origin and effective author identity. Preserve existing local work and account configuration.
2. With a clean worktree, fetch origin and create the assigned feature branch from the reviewed origin/main baseline. For example: `git fetch origin` then `git switch -c feature/subscription-workflows origin/main`. If a branch already exists, inspect it and continue it rather than recreating it. Before Gate A, prepare only work that does not invent a competing scaffold.
3. Implement the smallest complete slice within owned paths. Shared schema, dependencies, routing and contract changes require a request to their owner. Run the relevant checks and inspect the diff for secrets and ownership.
4. Update your named handoff with exact implementation commit(s), paths, tests and outcomes, remaining gaps and integration needs. Commit work using the actual participant's verified identity; do not invent emails or contribution records.
5. Push the feature branch with `git push -u origin HEAD` using that participant's existing authorized account. Open a PR targeting main with a feature-focused title, behavior changes, tests actually run and known gaps. Use the GitHub connector, browser or `gh pr create` only with the correct authorized account.
6. If PR creation is unavailable, prepare the title/body and GitHub comparison link for the pushed branch and ask Midhun P M to create the PR. A missing push permission is reported accurately; a local commit is not claimed as published. No global account switching is used as a workaround.
7. Midhun P M reviews and integrates small tested PRs. The team updates its feature branches from the reviewed main baseline without rewriting shared history. No direct application pushes to main, force pushes or automatic branch deletion.

## Written-source obligations and open event questions

S2 asks for repository creation/submission before 10:00 AM, at least hourly member pushes, each member's own contributions, current code on main, evaluator collaboration and an accessible functional demo video. S3 says code should be in a single branch and does not clearly explain temporary PR branches. The user-selected PR workflow above is authorized for implementation; it is not evidence that the organiser has clarified that wording.

Midhun P M records any organiser clarification, tool-use permission, portal confirmation and evaluator access in the decision/release records. These evidence fields remain unverified until actually checked. Names and SSH accounts alone do not establish individual contributions. Keep accurate attribution, participant review and limitations throughout delivery.

## Isolation

Use four independent clones with isolated virtual environments, frontend dependencies, databases, Compose project names and ports. Existing clone folder names and legacy SSH key filenames may remain technical paths. Keep shared root instructions consistent and explicitly load the named role file; instructions under team/ are not automatically discovered from the repository root.

Each person owns their named handoff. Local Git identities and any account-specific SSH commands belong only in the relevant clone configuration with the account holder's verified details. Preserve Midhun P M's existing default identity, HTTPS origin and authentication.

## Shared-file owners

| Area | Owner | Everyone else |
|---|---|---|
| Models/migrations/backend dependencies/API wiring | Midhun P M | Submit a change request |
| Frontend shell/routes/UI tokens/client/dependencies | Sherin Saji | Use exported primitives; request changes |
| Frozen documentation/contracts and integration | Midhun P M | Propose, do not overwrite |
| Subscription feature | Thanushree Suresh | Call its service boundary |
| Billing feature | Noel Biju | Call its service boundary |
| Own named handoff | Corresponding person | Read-only |

Thanushree Suresh and Noel Biju implement feature UI inside their own directories. Sherin Saji coordinates ownership transfer before changing those files during polishing. This preserves one owner per shared area without making Sherin Saji the only frontend developer.

## Handoff and integration checks

At every integration slice record the branch/commit, implemented behavior, touched paths, migration/dependency requests, tests and outcomes, manual verification, known gaps, contract changes and next dependency. A handoff is not proof of feature correctness.

Midhun P M checks diff/author identity, secrets, ownership, migration order, contracts, targeted tests, full app build and smoke flow before integration. Fetch before integrating. A shared-file conflict is resolved by its owner. Financial concurrency, browser, external-email and deployment checks require their own evidence.

After integration each teammate fetches the reviewed baseline and merges main into their feature branch as needed. Do not rebase already-shared commits or reset another person's work. Destructive cleanup and branch deletion require explicit approval.

## Gate A merge

The first documentation commit is ready for teammate onboarding, not full domain implementation. Midhun P M creates the backend models/migration, shared dependencies and importable module stubs; Sherin Saji creates shared frontend primitives, feature UI stubs and route imports. Both foundations must be integrated and boot together, the migration must apply, all feature imports must work and API/error/auth/amount shapes must agree before full subscription and billing work begins. Every domain branch then incorporates the same reviewed Gate A baseline.

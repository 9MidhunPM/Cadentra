# Integration, event constraints and collaboration

## Selected team workflow

Midhun P M coordinates the four-person team and reviews exact tested feature heads. The user's latest explicit policy replaces the earlier coordinator-created PR workflow: after a serialized GO, the feature owner merges locally and pushes main using their own verified SSH identity. No coordinator gh/API PR creation or merging is used for new slices.

The initial planning-pack commit and historical PRs remain part of the contribution history. Preserve those records and commit authorship; the current policy below governs subsequent delivery.

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
5. Publish the feature branch through its owner's SSH key and send Midhun P M the exact tested head, base, changed behavior, checks and remaining gaps through Codex TUI. Midhun P M reviews that immutable head; new commits invalidate the review until checked again.
6. Wait for Midhun P M's serialized GO naming the owner, reviewed feature head and expected remote main SHA. Only that owner holds the integration slot; all others wait. Fetch through the owner's existing SSH identity and verify remote main still equals the expected SHA. A changed base, extra feature commits, dirty worktree, conflict or failing check is reported before proceeding.
7. In the owner's clean independent clone, bring local main to the expected reviewed remote baseline with a fast-forward-only update, then merge the reviewed feature head locally while preserving original commits. Resolve conflicts only with the relevant owners and obtain renewed review of changed results. Run the integration checks on the local merge result before publishing.
8. Recheck remote main and publish local main with an ordinary non-force push through the owner's SSH key while holding the GO slot. If the remote has moved or the push is rejected, stop and report; do not force, reset or silently merge a new base. No global SSH, Git or gh configuration changes, token setup, API PR creation, branch deletion or unreviewed push is part of this procedure.
9. Verify the remote main SHA after the push, report the resulting merge SHA/checks to Midhun P M, and release the slot. Other contributors then fetch the reviewed main and update their feature branches without rewriting history.

## Current serialized checkpoint

On 31 October 2026 at 06:31 UTC, Thanushree Suresh's owner push was verified on main at 18e88ff. Midhun P M authorized Sherin Saji's production slice identified by head prefix 76ec next; that authorization is a queue checkpoint, not proof that it has been merged or deployed. Other owners wait for their own GO and expected remote SHA. Use the latest direct GO message and remote inspection rather than this snapshot when publishing.

## Written-source obligations and open event questions

S2 asks for repository creation/submission before 10:00 AM, at least hourly member pushes, each member's own contributions, current code on main, evaluator collaboration and an accessible functional demo video. S3 says code should be in a single branch and does not clearly explain temporary PR branches. The latest user-selected owner-merge/SSH-push workflow is authorized for implementation. Earlier PR contributions remain accurately recorded; neither workflow alone establishes organiser clarification of the single-branch wording.

Midhun P M records any organiser clarification, tool-use permission, portal confirmation and evaluator access in the decision/release records. These evidence fields remain unverified until actually checked. Names and SSH accounts alone do not establish individual contributions. Keep accurate attribution, participant review and limitations throughout delivery.

## Isolation

Use four independent clones with isolated virtual environments, frontend dependencies, databases, Compose project names and ports. Existing clone folder names and legacy SSH key filenames may remain technical paths. Keep shared root instructions consistent and explicitly load the named role file; instructions under team/ are not automatically discovered from the repository root.

Each person owns their named handoff. Local Git identities and any account-specific SSH commands belong only in the relevant clone configuration with the account holder's verified details. Preserve Midhun P M's existing default identity and authentication. The default SSH identity has been verified as 9MidhunPM without configuration changes. All three teammate SSH keys and write access are verified; see docs/13-GIT-IDENTITIES.md.

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

Midhun P M checks the exact tested feature head, diff/author identity, secrets, ownership, migration order, contracts, targeted tests, full app build and smoke flow before issuing the serialized GO. The owner tests the local merge result and publishes through their own SSH identity. Fetch before integrating. A shared-file conflict is resolved by its owner. Financial concurrency, browser, external-email and deployment checks require their own evidence.

After integration each teammate fetches the reviewed baseline and merges main into their feature branch as needed. Do not rebase already-shared commits or reset another person's work. Destructive cleanup and branch deletion require explicit approval.

## Gate A merge

The first documentation commit is ready for teammate onboarding, not full domain implementation. Midhun P M creates the backend models/migration, shared dependencies and importable module stubs; Sherin Saji creates shared frontend primitives, feature UI stubs and route imports. Both foundations must be integrated and boot together, the migration must apply, all feature imports must work and API/error/auth/amount shapes must agree before full subscription and billing work begins. Every domain branch then incorporates the same reviewed Gate A baseline.

## Hourly integration checkpoints

The user requested hourly branch integration on 31 October 2026. During active work each contributor checks reviewed origin/main at least hourly, incorporates it without rewriting history, and reports exact tested slice heads and dependencies. Midhun P M serializes owner GO slots with expected remote main SHAs and reports failures instead of integrating broken work to satisfy a timer. Ready slices may integrate earlier. This is the active team workflow, not an unattended system scheduler or proof of organiser compliance.

## Authorized demo deployment

The user authorized a workable demo on a Dokploy subdomain. Midhun P M is preparing cadentra.midhunpm.in; DNS resolution and project creation are recorded, but deployment is not yet verified. Do not label the demo live until deployment and public-origin smoke checks succeed. Deployment access and credentials remain private.

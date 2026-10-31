# Sources, requirements and proposal boundaries

## Source register

**S1: Challenge brief.** User-uploaded `Subscription_Management_System(3).pdf`, four pages. A copy is included as `references/Subscription_Management_System.pdf`. Page 1 defines the unified subscription business platform and Brightloop scenario. Page 2 specifies account requirements and roles. Page 3 specifies products, plans, quotations, subscription states and invoicing. Page 4 specifies discounts, payments and reporting/performance.

**S2: Organiser email, 28 October 2026.** Subject: “Event: Odoo x Make-A-Ton 9.0 Kochi Hackathon 2026”; sender: notifications@hackathon.odoo.com. Read through the user's connected inbox while preparing this pack. The message requires the portal timeline, repository creation/submission before 10:00 AM, individual code contributions and pushes at least hourly, latest code on main, evaluator collaborator access, and an open-access functional demo video with a stated maximum of 5 to 6 minutes. It describes a public repository as preferred. Use the portal's timezone/timeline rather than assuming the email specifies one. Do not redistribute the private message or its personalised unsubscribe URL.

**S3: Odoo Hackathon Participant Document.pdf.** Read through the connected Drive link in S2: https://drive.google.com/file/d/1Eg8PV2YTE__60a79HG3ASDZVKEnvQo1f/view . The document says participants use the GitHub IDs supplied at registration, only the team leader selects the problem statement, selection cannot subsequently be changed, and code should be in a single branch. It does not clearly explain whether short-lived feature branches/PRs are allowed during development.

**S4: Historical machine/setup statement.** Three extra Ed25519 key pairs were reported under the legacy filenames gh-agent2, gh-agent3 and gh-agent4. Public-key registration and authenticated accounts remain unverified. The earlier statement that no repository/workspace existed is superseded by S5. Preserve the existing Git identity and global configuration; existing key filenames are technical paths, not team roles.

**S5: User-approved team and implementation plan, 31 October 2026 (Asia/Kolkata).** The user assigned Platform & Catalog and coordination to Midhun P M, Subscription Workflows to Thanushree Suresh, Billing & Payments to Noel Biju, and Experience & Reporting to Sherin Saji. They accepted the React/Vite + FastAPI + PostgreSQL stack and documented billing policies. They selected independent clones, feature-named branches and PRs to main, with each teammate's assistant creating its own branch and opening a PR when ready or preparing the PR for Midhun P M to open. They explicitly approved one initial planning-pack push to main to establish the PR base. Subsequent application work uses feature branches and PRs.

The local checkout has origin https://github.com/9MidhunPM/Cadentra. Read-only remote inspection during planning returned no branch heads. The named-team planning baseline is recorded in the initial documentation commit; application code, migration and deployment evidence are still absent. Repository submission, evaluator access and the other participants' account access are not established by this setup.

## What has not been established

The complete participant video and external expectations video were not exhaustively reviewed to produce this package. Fetching the external expectations video as readable Drive content failed. No claim is made that this pack captures every video-only rule or announcement. Exact scoring weights, unrestricted autonomous-agent permission, a product naming policy and permission for remote PR branches are not established by the written sources above. Check portal/Discord clarifications before relying on those assumptions.

## Labels used throughout the pack

- **Required:** directly supported by S1, or an event obligation from S2/S3.
- **Proposed:** our engineering/product interpretation where sources are silent. User acceptance is recorded separately in the decision register; it does not make the choice an organiser rule.
- **Optional:** an enhancement, not a substitute for required scope.
- **Unverified:** not established from the sources reviewed.

Do not turn a proposed billing policy into an “Odoo rule.” Sources do not specify prorations, currencies, discount stacking, tax ordering, reset-token lifetime, payment gateway, framework, database or scheduler architecture.

## Technical references checked on 31 October 2026

- Codex guidance discovery: https://developers.openai.com/codex/guides/agents-md/ (redirects to ChatGPT Learn). Root and ancestor instruction discovery does not imply that all role files under team/ are automatically loaded; launch prompts explicitly request the correct file.
- Git local configuration and core.sshCommand: https://git-scm.com/docs/git-config . Environment GIT_SSH_COMMAND can override core.sshCommand.
- PostgreSQL uniqueness: https://www.postgresql.org/docs/current/ddl-constraints.html . Used for subscription-period and payment idempotency constraints.
- PostgreSQL locking: https://www.postgresql.org/docs/current/sql-select.html . Used for transaction-level concurrency design.

These references support engineering mechanics, not hackathon permission. No dependency version or measured performance result is claimed by this planning pack.

Additional technical references:

- GitHub SSH authentication test and its exit behavior: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/testing-your-ssh-connection
- GitHub account-specific SSH use: https://docs.github.com/en/account-and-profile/how-tos/account-management/managing-multiple-accounts
- GitHub CLI active-account behavior: https://cli.github.com/manual/gh_auth_status

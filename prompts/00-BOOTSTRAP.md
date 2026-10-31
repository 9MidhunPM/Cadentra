# Historical foundation reference: Gate A already verified locally

The backend and frontend foundations are integrated. This prompt records the original bootstrap responsibilities; it is not an instruction to reinitialize the current application. For current Platform & Catalog work, use prompts/01-PLATFORM.md and handoffs/RELEASE.md.

Read AGENTS.md, team/midhun-p-m/AGENTS.md, START_HERE.md, docs/03-ARCHITECTURE.md, docs/04-DATA-MODEL.md, docs/05-API-CONTRACT.md and docs/06-DOMAIN-RULES.md before changing shared infrastructure. Inspect the actual code, locks, migrations and latest tested commit first.

Midhun P M owns the backend foundation, shared models/migrations, actor/session and money/date helpers, error envelope, module wiring, health, standalone worker entry point and repeatable commands. Sherin Saji owns the shared frontend shell, components/client, transport and exports. Maintain the integrated baseline with reviewed additive changes; preserve isolated data, one migration history, request-scoped sessions and the standalone worker.

For a current fix, use a descriptive feature branch in the existing independent clone. Run applicable checks, record exact commit/results in the owner's handoff, and send the feature head plus expected main SHA to Midhun P M. Midhun P M reviews exact code/tests and issues serialized GO. The owner then rechecks main, performs the reviewed local merge and normally pushes main using their own verified SSH identity. Remote change, conflicts or a rejected push require stopping, refetching and renewed review. No force, branch deletion, history rewrite, unreviewed publication or coordinator gh/API PR integration.

Midhun P M's existing default SSH identity is verified as 9MidhunPM. Preserve global Git/SSH/auth settings and all existing credentials. Midhun P M owns the authorized Dokploy subdomain demo deployment; report actual runtime evidence rather than treating local foundation checks as deployment proof.

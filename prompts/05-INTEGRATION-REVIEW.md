Assist Midhun P M with read-only integration review first. Read AGENTS.md, docs/09-INTEGRATION.md, docs/10-TEST-PLAN.md, docs/15-REQUIREMENTS.md and each contributor's named handoff. Inspect the actual PR diff and commits; verify evidence rather than accept completion labels.

Check ownership, model/migration compatibility, API/service shapes, decimal arithmetic, date anchors, discount caps, invoice/payment idempotency, customer isolation, session/CSRF behavior, outbox semantics, dependencies and secrets. Identify conflicts and failing checks by severity and owner. Keep this review read-only, including credentials and branch protection.

After Midhun P M selects the ready PRs for integration, use the documented PR workflow, preserve accurate author history and avoid force pushes or destructive resets. Run affected checks plus the available full build/browser flow. Verify migrations against a clean disposable database. For Gate A, combine the backend and frontend foundations and verify them together before enabling dependent feature implementation.

Report the exact tested commit, executed commands/results, full-flow status, known requirements gaps, deployment evidence and next actions. Update handoffs/RELEASE.md for the coordinator only with verified evidence. A clean build does not establish financial correctness, customer isolation, real email delivery or performance.

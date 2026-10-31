Work on the Billing & Payments workstream assigned to Noel Biju, in the contributor's independent Cadentra clone. You are assisting the named contributor, not assuming another person's identity.

Read root AGENTS.md, explicitly read team/noel-biju/AGENTS.md, then START_HERE.md, docs/01-MVP.md, docs/05-API-CONTRACT.md, docs/06-DOMAIN-RULES.md and the references named by your role. Inspect the workspace and latest handoffs before editing; role files in team/ are not loaded automatically.

Follow root startup checks. Preserve dirty/unrelated work, inspect the remote/effective author, fetch origin, then create feature/billing-payments from reviewed origin/main in a clean checkout. If it exists, inspect its ancestry and continue without overwriting it. Subsequent slices use functionality-based feature branches, without participant names.

Before Gate A, validate the golden billing vectors and prepare scoped pricing and real PostgreSQL race tests. After the integrated Gate A baseline is verified, implement financial calculations, atomic recurring invoice generation, tax/discount configuration, partial/full payments, send/print and billing feature UI. Correctness takes priority over extras.

Stay within owned paths. Midhun P M owns models/migrations/backend wiring; Sherin Saji owns shared frontend routing/UI/client. Request shared changes through handoffs/noel-biju.md. Use existing agreed contracts and persisted data; placeholders remain visibly unimplemented until replaced by real behavior.

Implement the smallest complete slice, run actual applicable checks, inspect the diff, and update handoffs/noel-biju.md with the exact implementation commit, paths, commands/results, contract/migration requests and remaining gaps. Preserve accurate attribution and existing global Git/SSH/CLI settings; private credentials stay private.

Push the tested feature branch and open a PR targeting main through the intended authorized account. If PR creation is unavailable, prepare its title, description, validation results and comparison link, then ask Midhun P M to create it. No direct application pushes to main, force pushes, destructive cleanup, duplicate scaffolds or edits to other workstreams. The root instructions describe the one-time initial planning-pack main exception; it does not authorize later main pushes.

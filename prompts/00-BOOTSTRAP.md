Work on the shared backend foundation assigned to Midhun P M, Cadentra's Platform & Catalog owner and coordinator. This is the bootstrap phase; other contributors retain their feature ownership.

Read AGENTS.md, team/midhun-p-m/AGENTS.md, START_HERE.md, docs/00-SOURCES.md, docs/03-ARCHITECTURE.md, docs/04-DATA-MODEL.md, docs/05-API-CONTRACT.md and docs/06-DOMAIN-RULES.md.

Inspect the actual workspace, remote, branch, effective author and latest handoffs. The repository is 9MidhunPM/Cadentra and the user authorized its one-time initial planning-pack main commit/push. Application work must start on feature/platform-foundation from the reviewed main baseline, following the root startup checks. Do not regenerate keys, create another remote, change global credentials, read private keys or overwrite existing work.

The React/Vite + FastAPI + PostgreSQL stack and documented billing policies are approved. Resolve compatible dependency versions, pin them and record them. Coordinate with Sherin Saji, who owns the frontend foundation on feature/frontend-foundation. Thanushree Suresh and Noel Biju prepare contracts/tests until the integrated Gate A baseline is verified.

Implement Gate A: FastAPI structure, PostgreSQL/session setup, all agreed ORM models, one reviewed initial Alembic migration, shared actor/auth dependencies, error envelope, money/date helpers, importable feature router stubs, health endpoint, test scaffolding and Make commands. Coordinate same-origin API/auth and stable exports with Sherin Saji. Keep placeholder endpoints visibly unimplemented; never return fake successful data.

Wire one standalone worker entry point, not a scheduler inside each API process. Use isolated test/demo databases and non-secret env templates; preserve existing data and volumes. Provide make dev, make test, make lint, make seed-demo and make smoke with honest behavior and documented prerequisites.

Run startup/import/migration checks and actual available tests. Inspect ownership and secrets. Update handoffs/midhun-p-m.md with exact implementation commit, commands/results, migration revision, module exports and blockers. Push the feature branch and open a PR targeting main; if unavailable, prepare the PR details/comparison link and ask Midhun P M to create it. Release the smallest usable baseline before expanding into full auth/catalog. Gate A passes only once both foundations are integrated and their combined startup, migration and interfaces are verified.

# Cadentra

**Every subscription. Every cycle. Accounted for.**

Cadentra is a proposed unified subscription management platform for the **Subscription Management System** hackathon challenge. The demonstration business is **Brightloop Software**.

## Status

The backend foundation implements persistent identity/customer/catalog APIs, shared ORM models, Alembic migrations, explicit worker wiring and an SMTP outbox. The shared frontend foundation is reviewed and integrated; business screens are still placeholders. Integrated Gate A verification is recorded in the release handoff before domain implementation is declared ready.

## Product scope

- Role-based administration, staff tools and a customer portal.
- Products, price-adjusting variants and daily/weekly/monthly/yearly plans.
- Quotation templates and the required subscription lifecycle.
- Recurring invoices, automatic taxes and eligible discounts.
- Invoice-linked payments, balances, overdue tracking and reporting.
- Optional CycleGuard billing-health explanations.

## Development

Start with [START_HERE.md](START_HERE.md). The approved stack is React + Vite + TypeScript, FastAPI, PostgreSQL and Docker Compose. This is an intentional simplification of the earlier Next.js suggestion: one client application and one backend own all business logic. The user approved this baseline; Midhun P M coordinates changes and the Gate A freeze.

Dependency versions are not fabricated here. Resolve mutually compatible maintained versions once during bootstrap, pin them in lockfiles and record them in `docs/14-DECISIONS.md`.

## Team and collaboration

| Contributor | Workstream | Startup prompt |
|---|---|---|
| Midhun P M | Coordination, Platform & Catalog | `prompts/00-BOOTSTRAP.md` |
| Thanushree Suresh | Subscription Workflows | `prompts/02-SUBSCRIPTIONS.md` |
| Noel Biju | Billing & Payments | `prompts/03-BILLING.md` |
| Sherin Saji | Experience & Reporting | `prompts/04-EXPERIENCE.md` |

Use independent clones and feature-named branches. Open a PR to `main` after checks, or prepare the PR details and ask Midhun P M to create it. The team is implementing its feature slices; consult the latest release and contributor handoffs for Gate A evidence. See [START_HERE.md](START_HERE.md) for what each person can begin now.

## Required implementation commands

The backend now provides `make dev`, `make test`, `make lint`, `make seed-demo`, and `make smoke`. See [runtime instructions](docs/16-RUNTIME.md) for Compose/native prerequisites and explicit disposable test databases. Planning fixtures can also be checked independently:

```sh
python3 scripts/check_pack.py
```

## Submission record

Fill in only after verification:

- Portal-selected problem statement: Subscription Management System
- Approved app/repository name: Cadentra; `9MidhunPM/Cadentra`
- Deployment URL: not deployed
- Demonstration video: not recorded
- Tested commit: see `handoffs/RELEASE.md` (checks and remaining gaps recorded separately)
- Implemented requirements and remaining gaps: `docs/15-REQUIREMENTS.md`
- Team: Midhun P M, Thanushree Suresh, Noel Biju, Sherin Saji; record contributions as they land

Do not include passwords, private keys, tokens, personal email bodies or private organiser correspondence in the public repository.

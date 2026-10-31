# Cadentra

**Every subscription. Every cycle. Accounted for.**

Cadentra is a proposed unified subscription management platform for the **Subscription Management System** hackathon challenge. The demonstration business is **Brightloop Software**.

## Status

This repository currently contains the planning pack only. Features below are planned, not claimed as implemented. Replace this status with verified functionality as work lands.

## Planned product

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

Use independent clones and feature-named branches. Open a PR to `main` after checks, or prepare the PR details and ask Midhun P M to create it. The planning pack is ready for onboarding; application Gate A is still pending. See [START_HERE.md](START_HERE.md) for what each person can begin now.

## Required implementation commands

Midhun P M must create and verify `make dev`, `make test`, `make lint`, `make seed-demo`, and `make smoke`. These commands do not exist yet. The only executable check included now is:

```sh
python3 scripts/check_pack.py
```

## Submission record

Fill in only after verification:

- Portal-selected problem statement: Subscription Management System
- Approved app/repository name: Cadentra; `9MidhunPM/Cadentra`
- Deployment URL: not deployed
- Demonstration video: not recorded
- Tested commit: not implemented
- Implemented requirements and remaining gaps: `docs/15-REQUIREMENTS.md`
- Team: Midhun P M, Thanushree Suresh, Noel Biju, Sherin Saji; record contributions as they land

Do not include passwords, private keys, tokens, personal email bodies or private organiser correspondence in the public repository.

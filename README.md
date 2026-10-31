# Cadentra

**Every subscription. Every cycle. Accounted for.**

Cadentra is a subscription management platform for the **Subscription Management System** hackathon challenge. The demonstration business is **Brightloop Software**.

## Status

The existing public demo at [cadentra.midhunpm.in](https://cadentra.midhunpm.in) is healthy on migration `0002` at `b662117`. Its 11/11 public API acceptance and desktop/mobile checks are historical baseline evidence, recorded separately in [release evidence](handoffs/RELEASE.md).

Midhun P M's primary coordinator assistant and seven scoped helper tasks are building and reviewing a cinematic release candidate: a homepage and `/app` routing, CycleGuard API/UI, startup-log redaction, exact migration readiness, safe pagination, form/send recovery, and production Resend SMTP on port 587 with STARTTLS. **This candidate has not been deployed.** Helper tasks assist the existing four-person team and do not establish new individual human activity. Focused candidate checks have separate scopes; the historical 393-backend/164-frontend totals are not claimed as a new combined rerun.

Twenty of 23 requirement groups retain scoped verification. Three remain partial: external password-reset delivery, external invoice delivery, and final performance. The user confirmed Resend password and sender/FROM configuration are missing, so no external delivery is verified. The native all-page T30 attempt is paused after 55 passes and a sign-in timeout on case 56; it does not prove the final every-page two-second target. E01–E04 event obligations remain unverified. Root will update deployment state after actual candidate verification.

## Product scope

- Role-based administration, staff tools and a customer portal.
- Products, price-adjusting variants and daily/weekly/monthly/yearly plans.
- Quotation templates and the required subscription lifecycle.
- Recurring invoices, automatic taxes and eligible discounts.
- Invoice-linked payments, balances, overdue tracking and reporting.
- Optional CycleGuard billing-health explanations.

## Development

Start with [START_HERE.md](START_HERE.md). The approved stack is React + Vite + TypeScript, FastAPI, PostgreSQL and Docker Compose. This is an intentional simplification of the earlier Next.js suggestion: one client application and one backend own all business logic. The user approved this baseline; Midhun P M coordinates changes and the Gate A freeze.

Use Python3.12, uv, Node>=22.12 and PostgreSQL18.6. Install committed dependency locks with `make sync` and `npm --prefix frontend ci`; exact resolved versions are recorded in [runtime instructions](docs/16-RUNTIME.md) and `docs/14-DECISIONS.md`.

## Team and collaboration

| Contributor | Workstream | Startup prompt |
|---|---|---|
| Midhun P M | Coordination, Platform & Catalog | `prompts/00-BOOTSTRAP.md` |
| Thanushree Suresh | Subscription Workflows | `prompts/02-SUBSCRIPTIONS.md` |
| Noel Biju | Billing & Payments | `prompts/03-BILLING.md` |
| Sherin Saji | Experience & Reporting | `prompts/04-EXPERIENCE.md` |

Use independent clones and feature-named branches. Midhun P M reviews the exact tested feature head, then issues a serialized GO naming the owner and expected remote main SHA. The owner merges locally, tests the result and pushes main through their own verified SSH identity; the other owners wait for their GO. The current workflow uses no coordinator gh/API PR creation or merging, and preserves historical PR/commit attribution. See [integration instructions](docs/09-INTEGRATION.md) and [START_HERE.md](START_HERE.md) for delivery and startup details.

## Required implementation commands

The backend now provides `make dev`, `make test`, `make lint`, `make seed-demo`, and `make smoke`. See [runtime instructions](docs/16-RUNTIME.md) for Compose/native prerequisites and explicit disposable test databases. Planning fixtures can also be checked independently:

```sh
python3 scripts/check_pack.py
```

## Submission record

Fill in only after verification:

- Portal-selected problem statement: Subscription Management System
- Approved app/repository name: Cadentra; `9MidhunPM/Cadentra`
- Existing demo: `https://cadentra.midhunpm.in`, healthy baseline `b662117`; cinematic candidate not yet deployed
- Demonstration video: not recorded
- Tested commit: see `handoffs/RELEASE.md` (checks and remaining gaps recorded separately)
- Implemented requirements and remaining gaps: `docs/15-REQUIREMENTS.md`
- Current project/team status: [single HTML report](frontend/public/PROJECT_STATUS.html), also served at `/PROJECT_STATUS.html`
- Team: Midhun P M, Thanushree Suresh, Noel Biju, Sherin Saji; record contributions as they land

Do not include passwords, private keys, tokens, personal email bodies or private organiser correspondence in the public repository.

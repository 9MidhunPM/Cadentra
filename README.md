# Cadentra

**Every subscription. Every cycle. Accounted for.**

Cadentra is a subscription management platform for the **Subscription Management System** hackathon challenge. The demonstration business is **Brightloop Software**.

## Status

The cinematic website and working application are live at [cadentra.midhunpm.in](https://cadentra.midhunpm.in); [Open app](https://cadentra.midhunpm.in/app) enters the authenticated workspace. Application release `5895b04` is deployed and verified: public homepage, sign-in, overview, all three CycleGuard categories, persisted invoice, desktop/mobile navigation/theme and logout passed. API/database are healthy on migration `0002`, with one running worker.

Midhun P M remains primary coordinator. Seven bounded helper tasks assisted the cinematic homepage, route splitting, CycleGuard, recovery and security work; this does not invent additional human contributions. Focused checks, build/type/lint and independent reviews passed. Earlier393-backend/164-frontend/full-T31 evidence remains separately scoped; no repeated whole-suite run is claimed.

Twenty of23 required product groups have scoped verification. External reset delivery, external invoice delivery and final every-page performance remain partial. Production is prepared for Resend SMTP587 with certificate-verified STARTTLS, but the user has not yet supplied the private key/sender. Missing configuration fails safely before connection; no external delivery is claimed. Development Mailpit is unchanged. The previous native all-page run stopped after55 passes and a sign-in timeout on case56. Event obligations remain unverified. See the [single status page](https://cadentra.midhunpm.in/PROJECT_STATUS.html) and [release evidence](handoffs/RELEASE.md).

The still-render website is usable now. An optional hero-video generation prompt is in [HERO_VIDEO_PROMPT.md](frontend/design/HERO_VIDEO_PROMPT.md).

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
- Live demo: `https://cadentra.midhunpm.in`, verified cinematic application `5895b04`
- Demonstration video: not recorded
- Tested commit: see `handoffs/RELEASE.md` (checks and remaining gaps recorded separately)
- Implemented requirements and remaining gaps: `docs/15-REQUIREMENTS.md`
- Current project/team status: [single HTML report](frontend/public/PROJECT_STATUS.html), also served at `/PROJECT_STATUS.html`
- Team: Midhun P M, Thanushree Suresh, Noel Biju, Sherin Saji; record contributions as they land

Do not include passwords, private keys, tokens, personal email bodies or private organiser correspondence in the public repository.

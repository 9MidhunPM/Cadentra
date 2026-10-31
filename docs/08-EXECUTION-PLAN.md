# Eight-hour execution plan

Relative to the actual permitted coding start. This is a proposed work allocation, not an organiser timetable or guarantee. The portal timeline wins. Repository submission cannot wait for this engineering plan to finish.

| Window | Target | Parallel work | Exit evidence |
|---|---|---|---|
| 0:00-0:20 | Decisions and safety | Midhun P M handles portal/repository checks and scaffold; Thanushree Suresh reviews lifecycle; Noel Biju reviews billing vectors; Sherin Saji prepares UI shell | Stack/contract owners fixed; publishing mode recorded; no global credentials altered |
| 0:20-0:55 | Gate A: shared foundation | Midhun P M models/migration/auth dependencies/module stubs; Sherin Saji frontend shell/primitives/client; Thanushree Suresh/Noel Biju write tests against agreed contracts | DB migration applies; frontend/API boot; stable module imports; shared commit integrated |
| 0:55-2:00 | First vertical slices | Midhun P M auth/catalog; Thanushree Suresh template + subscription draft/quote; Noel Biju calculator/invoice service; Sherin Saji reporting/portal shells + E2E harness | Login + real catalog creation + API-backed first forms; initial deployment |
| 2:00-3:30 | Connect lifecycle to billing | Midhun P M roles/reset email; Thanushree Suresh confirm/activate/cadence/policy actions; Noel Biju due worker/tax/discount/payment; Sherin Saji portal ownership and overview | Full subscription-to-invoice flow with real data |
| 3:30-4:30 | Money and permissions gate | Partial/full payment; simultaneous bill runs; staff restrictions; two-customer isolation; email verification | Core end-to-end browser test and financial tests pass |
| 4:30-5:45 | Required coverage | Complete templates, all cadences, lifecycle flags, automatic discounts, sending/printing, filters | Requirement matrix checked with evidence, not optimistic labels |
| 5:45-6:15 | Optional window only if core green | Invoice explanation and small CycleGuard panel; seed substantial dataset | Extras must not break core; performance results recorded |
| 6:15-7:15 | Freeze and harden | Fix integration/security/data errors; run fresh-clone setup; deploy final candidate | One evaluated branch, reproducible startup, passing critical checks |
| 7:15-8:00 | Demo and submission | Record real functional flow; README/gaps/contributions; verify public video access and portal confirmation | Tested commit and final evidence recorded before portal deadline |

## Start from the first planning commit

The documentation commit establishes main and is not Gate A. Read START_HERE.md and the assigned team role, create a feature-named branch from reviewed origin/main in your independent clone, and follow docs/09-INTEGRATION.md for PR delivery. Midhun P M starts feature/platform-foundation; Sherin Saji starts feature/frontend-foundation. Thanushree Suresh and Noel Biju may review contracts and prepare domain test cases on feature/subscription-workflows and feature/billing-payments. Full domain implementation waits for the shared Gate A baseline; no second scaffold is created.

## Midhun P M: coordinator responsibilities

Review Gate A and all contract changes. Run the complete product regularly. Integrate small working slices every 20-30 minutes when feasible, with the required hourly contribution rhythm as an external constraint. Check that each participant understands and accurately owns their contribution. Review feature PRs and merge tested slices into main so the evaluated code stays current. A teammate assistant opens its PR when authorized; if unavailable, it supplies the prepared PR details to Midhun P M. Record the actual tested commit.

## Team delivery slices

Midhun P M: foundation -> auth -> catalog UI/API -> SMTP/reset -> deployment/migration fixes.
Thanushree Suresh: cadence/lifecycle tests -> draft/quotation/templates -> active flow -> pause/close/renew -> subscription UI completion.
Noel Biju: pricing vectors -> invoice/period uniqueness -> discounts/taxes -> payments -> worker/outbox/print tests.
Sherin Saji: shared UI/client -> dashboard/portal reads -> safe portal actions -> browser checks -> optional CycleGuard.

## At hour 2, if the app does not boot together

Stop new feature work. Midhun P M and the affected owners fix module wiring, migrations, cookie/proxy configuration and incompatible response shapes. A successful isolated unit test is not proof that the product works.

## At hour 4, if the complete core flow is broken

Freeze all optional work immediately. Finish one real customer -> subscription -> invoice -> payment -> portal flow. Retain explicit gaps for other source requirements. Do not substitute static JSON or success toasts for missing behavior.

## At hour 6

No new architecture, libraries, gateway, chatbot or redesign. Changes must fix correctness, required coverage, deployment or demonstrated usability. Record any uncompleted requirement honestly. Rehearse a backup local demo, but do not present it as deployed.

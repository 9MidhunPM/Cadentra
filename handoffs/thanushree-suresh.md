# Thanushree Suresh: handoff

Status: PRE-GATE A ACCEPTANCE CASES PREPARED; APPLICATION PENDING

Role: Subscription Workflows
Branch: feature/subscription-workflows
Baseline: 766cb2664ded48afcb1012001565cbbf65c68142
Setup commit: c4ea2e4abc22e59790afd51c395249bb7b343aa8 (pushed through gh-agent2)
Preparation commit: 208adf0a0bdb2d384da15e4186e0d5e2be3afd2c
Application commit: NONE

## Delivered slice
Created the subscription feature branch from the reviewed main baseline. Verified
the existing Git author configuration and authenticated the requested gh-agent2
SSH key as thanushreesuresh. The setup checkpoint was pushed successfully before
feature preparation began. No production module has been created.

Prepared independent calendar fixtures and declarative lifecycle scenarios under
the owned subscription tests. The README maps them to acceptance IDs and explains
how to bind them to the actual services after Gate A. Scenario execution and all
application acceptance results remain NOT RUN.

## Files changed
handoffs/thanushree-suresh.md
backend/tests/subscriptions/README.md
backend/tests/subscriptions/calendar_cases.json
backend/tests/subscriptions/check_prepared_cases.py
backend/tests/subscriptions/lifecycle.feature

## Tests actually run
- `python3 scripts/check_pack.py`: PASS (planning structure, fixtures and examples only).
- `bash scripts/preflight.sh`: exit 0; Docker unavailable in this environment.
- `python3 backend/tests/subscriptions/check_prepared_cases.py`: PASS; 12 boundary
  cases (43 expected dates), 6 eligible period cases, and all four unchanged
  canonical fixtures compared with the planning reference only.
- `git diff --check`: PASS. Read-only review of the scenario inventory found 15
  scenarios and 6 outlines (35 expanded cases); no Gherkin steps were executed.
- `python3 -m compileall -q backend/tests/subscriptions`: PASS.
- Inline standard-library negative controls with temporary copies: the asset
  validator rejected month-end drift, duplicate IDs, a missing canonical fixture
  and a period starting at expiry. Repository fixtures were not changed.
- Independent standards and specification reviews: no remaining blocking
  findings. Corrected the shortened-period scenario to process cycle 0 before
  billing cycle 1 on its due date.
- SSH authentication with gh-agent2: GitHub identified thanushreesuresh. GitHub's
  expected no-shell exit status was 1. The setup branch push succeeded.

## Manual verification
Application verification not performed; the shared foundation is not implemented.

## Required shared changes
Requests for Gate A agreement; these are not newly approved contracts:

| Owner | Request | Reason and test impact |
|---|---|---|
| Midhun P M | Export concrete synchronous Session, Actor, clock, error and model dependencies and the disposable PostgreSQL test fixtures. | Bind tests to actual services; do not create alternate fixtures or models. |
| Midhun P M + Noel Biju | Agree the cycle snapshot fields/types for original start, cadence, exclusive end and optional close cap; freeze the billable-input result with immutable line/plan pricing inputs. | Bind T09/T13 and worker use without guessing the conceptual signatures. |
| Midhun P M + Noel Biju | Name the transaction owner for apply_action/process_lifecycle and agree use of billing's subscription-row lock for edits/pause/close. Preserve due outcomes before final closure. | T33/T34 and concurrent billing-versus-action checks must use real transactions and the same lock discipline. |
| Midhun P M | Specify whether a template supplies omitted lines or explicit lines replace them, how plan/template mismatch is handled, and which start/end/terms/line fields may change in each state. | SubscriptionCreate currently has both template_id and lines; avoid incompatible behavior or repricing. |
| Midhun P M | Define quotation_valid_until as a date or timestamp and its exact confirmation boundary; define the basis and boundary for plan availability validation. | Prepare before/at/after deadline and availability tests only after the policy is recorded. Existing cases use unambiguously expired dates. |
| Sherin Saji | Provide exact route factory, API/error/session client and shared UI exports; agree safe portal detail projection and delegated action result. | Implement feature UI and T06/T31 without changing shared routing or duplicating portal logic. |

No additive migration is requested yet. If agreed types reveal missing persistent
fields, request type, nullability, default and rationale before implementation.

## Known gaps and next dependency
Application implementation awaits the integrated, verified Gate A baseline.
There are no application models, services, dependency lockfiles or test harness
on this main baseline. Docker is unavailable in this environment. No application,
PostgreSQL, concurrency, browser, deployment or email check has been performed.

The connected GitHub API account is 9MidhunPM; SSH push authentication is the
verified thanushreesuresh account. API account identity is not inferred from SSH.
If a participant-authenticated PR session is unavailable, Midhun P M can create
the prepared PR from the comparison link below without global account switching.

## Next slice
After the integrated Gate A baseline is verified, bind the prepared cases to the
agreed services, implement calendar/lifecycle validation and the persisted
template -> draft -> quotation -> confirmation -> activation slice. Follow with
staff UI and policy actions. Keep commits atomic and checkpoint active work at
least every 30 minutes, as requested by the user.

## Prepared PR

Title: test(subscriptions): prepare calendar and lifecycle acceptance cases

Target: main

Comparison: https://github.com/9MidhunPM/Cadentra/compare/main...feature/subscription-workflows

Description: Prepare subscription calendar fixtures and lifecycle acceptance
scenarios before Gate A. Preserve the canonical cadence fixtures and cover
snapshot isolation, policy actions, backlog-safe closure and customer isolation.
Record explicit service/interface requests for the foundation owners. These are
prepared test assets; application behavior is not implemented or verified.

Validation for PR: planning-pack check, prepared-calendar checker, Python
compilation, whitespace check and independent reviews passed. Lifecycle scenarios
have no runtime bindings; PostgreSQL/concurrency/browser checks remain NOT RUN.

# Thanushree Suresh: Subscription Workflows

Read the repository-root AGENTS.md first. Work on behalf of Thanushree Suresh within this role; this assignment does not change Git identity or authorize impersonation. This file adds scope to shared instructions.

Historical initial branch: `feature/subscription-workflows` (already used; preserve its history). Gate A passed locally. Inspect the current checkout and release evidence, fetch origin and continue the existing application on a descriptive feature branch from reviewed main. Do not recreate foundations. Deliver through the root workflow: exact code/test review by Midhun P M, serialized GO tied to the expected main SHA, then the owner's local reviewed merge and normal SSH push to main using their verified identity. No PR/API integration or global auth changes.

## Owned paths
backend/app/modules/subscriptions/, backend/tests/subscriptions/, frontend/src/features/subscriptions/, matching feature browser/unit tests, handoffs/thanushree-suresh.md.

## Mission
Implement quotation templates, subscription records, calendar schedule semantics, required lifecycle and plan-controlled actions, together with their staff-facing screens. Do not build a separate frontend shell or independent invoice service.

## Dependency boundary
Gate A is locally verified. Use Midhun P M's models/session/actor dependencies and Sherin Saji's shared client/UI. Request missing fields rather than editing shared models/migrations. Use the frozen date/price policy, not a library's accidental behavior.

## Delivery sequence
1. Pure calendar helpers and state-transition tests for four cadences, month-end and leap dates.
2. Template CRUD; draft creation/line validation; quotation validity; confirmation snapshots; activation.
3. Staff-facing list/detail/template/quotation UI connected to actual APIs.
4. Pause/resume/early-close/expiry/renewal and active next-cycle line changes, with effective dates and audit records.
5. Expose lifecycle service functions for Noel Biju worker and Sherin Saji portal; help test cross-customer actions.

## Non-negotiable behaviours
Required primary states remain DRAFT, QUOTATION, CONFIRMED, ACTIVE, CLOSED. Pause is a separate schedule condition. Never skip confirmation. Renew creates a new linked draft; CLOSED is terminal. Count product quantities, not base-fee lines. Block changes if unprocessed due periods would otherwise be repriced. Keep original date anchors, not drifted month additions.

The lifecycle worker must not finalize expiry closure before earlier due cycles are handled. Coordinate this with Noel Biju and test worker downtime. Activation does not directly create invoices; the shared due worker/run action does so.

## Tests and done
T09-T13, T33-T34 and your contribution to T06/T31 pass against actual services. Customer-owned action services enforce both ownership and policy. Forms show server errors and reflect effective dates. Detail reload preserves state. Handoff includes service signatures, sample requests, tests actually run and missing migrations.

## Exclusions
No changes to shared models, central backend wiring, shared UI, other feature directories or billing/payment arithmetic. No destructive Git operations. Publish only through the root review/GO and owner-operated local merge/SSH main-push workflow.

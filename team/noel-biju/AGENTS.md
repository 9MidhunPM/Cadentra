# Noel Biju: Billing & Payments

Read the repository-root AGENTS.md first. Work on behalf of Noel Biju within this role; this assignment does not change Git identity or authorize impersonation. This file adds scope to shared instructions.

Initial feature branch: `feature/billing-payments`. In your assigned independent clone, follow the root startup checks, fetch origin, and create this branch from reviewed origin/main. Keep an existing branch only after inspecting it. Deliver through a PR targeting main; follow the root fallback if PR creation is unavailable.

## Owned paths
backend/app/modules/billing/, backend/tests/billing/, frontend/src/features/billing/, corresponding feature tests, handoffs/noel-biju.md.

## Mission
Implement correct recurring invoices, tax/discount rules, payment recording, print/email operations and the staff-facing billing screens. The strongest correctness budget belongs here. Do not build a live payment gateway.

## Dependency boundary
Before Gate A, verify billing vectors and prepare concurrency test designs. After Gate A use Midhun P M's models, session factory and money helpers plus Thanushree Suresh's immutable period inputs. Midhun P M owns migration and worker wiring; request additions explicitly. Sherin Saji owns shared primitives/client and reporting.

## Delivery sequence
1. Pure pricing/discount-allocation/tax calculation tests matching contracts/billing-vectors.json.
2. One-transaction due-period issuance with PostgreSQL uniqueness, row locks, immutable snapshots and catch-up.
3. Admin-only taxes and discounts, scope/minimum/date/cap logic, concurrency-safe usage selection.
4. Invoice detail/confirm/cancel/send/print, manual partial/full payments with idempotency and row locks.
5. Billing feature UI and standalone worker/outbox integration; help Sherin Saji reconcile reports.

## Non-negotiable behaviours
Never use floats or client-supplied totals. Never advance a schedule cursor without a durable period outcome. Never “check then insert” outside a protected transaction to avoid duplicate invoices. Retries must not consume an extra discount use. A failed uniqueness insert must not leave the PostgreSQL transaction unusable. Do not auto-reinvoice cancelled periods or mutate past invoices.

Replay a matching payment request before rejecting a now-paid invoice. Reject conflicting key reuse and overpayment. Paid/partial cancellation is outside the supported no-refund scope. Email retries may duplicate transport delivery but must never create another invoice/payment. Distinguish queued from delivered.

## Required tests
T08, T14-T27, plus expiry/catch-up coordination in T13/T34. At least one true two-connection race test each for recurring invoicing, capped discounts and payments. Sequential duplicate calls alone are insufficient. Test a rollback before commit. Golden total is 4970.16, then 2000.00/2970.16 payments.

## Handoff
Include exact expected totals, tested concurrency outcomes, invoice/payment schemas, safe print function for portal reuse, outbox status behavior, commit and executed commands. Flag any missing safety test rather than claiming production-grade billing.

## Exclusions
No new schema/migrations, global dependency changes, reporting rewrites, shared UI edits, direct main pushes, account switching, fake card processing or tax-law compliance claims.

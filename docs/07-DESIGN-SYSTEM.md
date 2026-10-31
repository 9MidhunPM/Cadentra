# Experience and design brief

Proposed direction, not a design supplied by the organiser. Product name: **Cadentra**. Tagline: **Every subscription. Every cycle. Accounted for.** Brightloop Software is the demonstration organisation.

## Visual direction

The user selected Graphite Mint as the default dark theme and Sage Commerce as light mode. Use one semantic component system and the tokens in frontend/src/styles/global.css. The selected concepts and source explanation live in frontend/design/README.md; their illustrative figures are not production metrics.

Graphite Mint uses near-black workspaces, charcoal surfaces and mint accents. Sage Commerce uses pale sage workspaces/navigation, white surfaces, a charcoal header and forest-green actions. Theme preference is local and contains no account data. Preserve clear financial tables, tabular numerals, readable labels, keyboard focus and semantic status colors. Feature modules use shared controls and var(--color-*) tokens rather than inventing palettes.

Motion is short and purposeful: navigation selection, mobile drawer and dialog feedback; respect reduced motion and keep financial actions immediate. Ctrl/Cmd K navigates actual role-permitted pages. No decorative controls or preview chart totals become fake application functionality.

## Navigation and screens

Staff navigation: Overview; Customers; Catalog (Products, Plans); Subscriptions (list, templates); Billing (Invoices, Taxes, Discounts); Settings (staff, admin only). Customer navigation: My subscriptions; My invoices; Account. Keep role contexts visibly distinct.

Overview: one compact metric strip; a revenue/payments time series only when backed by real API data; an overdue-invoices table; optional CycleGuard side panel. Use a workspace/table layout rather than a marketing landing page or a grid of decorative cards. Primary action: New subscription. Secondary operator action: Run due billing.

Subscriptions list: customer, reference, plan, primary state, pause/expiry label, next billing date and amount. Filters plus pagination. Detail: lifecycle stepper, dates, line items, plan policies, invoice history and allowed actions. Use a side drawer for simple product/plan edits; use a full page for a multi-line quotation.

Invoices list: reference, customer, service period, total, paid, balance, due date, status. Detail: printable document body, totals and payment history. “Explain total” opens the actual line calculation snapshot. Confirm, send, print and record payment actions must expose real loading/success/error states.

Customer portal: readable subscription summaries and invoice table. Show the exact effective date of pause/close/resume. Never display a false “pay now” checkout if only manual recording is implemented.

## Reusable components, owned by Sherin Saji

AppShell; RoleGuard display wrapper; PageHeader; DataTable with pagination; Money; DateLabel; StatusBadge; FormField; ConfirmDialog; EmptyState; ErrorPanel; LoadingSkeleton; SubscriptionStepper; Toast; API error translator. Backend authorization remains authoritative. Feature owners use these primitives without redefining a design system.

## Interaction rules

One clear primary action per screen. Disable a pending submit to reduce accidental repeats, but rely on backend idempotency for correctness. Every form has labels, inline validation and useful errors. Preserve entered values after a failed request. Successful mutations invalidate/refetch relevant records. Never use a client-only role switch as real authentication.

A computed field shows currency and an explanation, not a mysterious total. Date filters display inclusive/exclusive semantics in understandable text. Human-readable UI can say “through 30 November” while storing exclusive 1 December.

## Responsive and accessibility checks

Test at a common laptop viewport and a narrow mobile viewport. Navigation collapses; wide financial tables get deliberate horizontal scrolling without clipping actions. Support keyboard operation, focus return from modals, proper labels, contrast and reduced motion. Do not make status distinguishable only by colour. Avoid gratuitous animation.

## Demo data

Display real database seed records, visibly identified as demo data. Never hard-code a “$250k revenue” chart. Seed a due cycle, overdue invoice, paid invoice and paused subscription so real features are visible without external providers. Seed timestamps are derived from the configured test/demo date, not permanently fixed to a past event day.

## Design completion evidence

Capture the main workflow at desktop and mobile widths after it runs. Check typography, alignment, clipped amounts, loading states, empty states, forbidden pages, printable invoices and successful persisted mutations. Visual approval and functional tests are separate checks.

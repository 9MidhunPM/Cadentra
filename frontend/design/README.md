# Approved Cadentra interface direction

On 31 October 2026 the user rejected the initial navy/teal concepts and selected Graphite Mint as the primary dark theme and Sage Commerce as light mode. The preview images beside this document were generated with the built-in image tool and explicitly selected by the user. They contain labelled illustrative data; they are design references, not production data or bundled application screenshots.

## Product and visual contract

Cadentra helps Brightloop staff follow subscriptions, invoices and payments, and lets customers manage only their own records. The interface supports everyday operations: readable financial tables, clear effective dates, distinguishable payment/invoice metrics, safe actions and honest loading/error/empty states.

Graphite Mint uses a near-black workspace, charcoal surfaces and mint selection/actions. Sage Commerce uses a pale sage workspace/sidebar, true-white surfaces, a charcoal header and forest-green actions. The implementation shares one component system and semantic CSS tokens across both modes. Dark is the first-visit default; a user-selected light/dark preference persists locally. Theme storage contains no account or financial data.

The shared shell uses a compact persistent header, a 248px navigation column, precise system typography, tabular money and code-native icons. Page search is a working Ctrl/Cmd K navigation dialog, filtered by the current account role; it does not pretend to search customer data. Theme and sign-out controls are functional. Static mockup account names are replaced by the authenticated actor. Notification bells and organisation switchers are omitted until there is real functionality behind them.

## Motion contract

- Focal interaction: the active navigation surface travels between destinations with a short damped spring, preserving orientation.
- Mobile: interruptible spring drawer, softly dimmed background, trapped keyboard focus, Escape dismissal and focus return.
- Feedback: immediate press compression, subtle hover tone, quick theme-icon transition, and calm dialog arrival with a faster exit.
- Reduced motion disables layout/transform movement; controls remain fully usable. No looping decorative animation or delayed financial action is introduced.
- Motion features load in a separate chunk; no persistent animation loop is used for the shell.

## Verification and remaining fidelity work

The initial theme implementation was compared against both selected concepts at 1497x1049 desktop and 390px mobile widths. Palette, navigation hierarchy, typography, control geometry, focus, spacing and clipping were inspected. A visible outline around programmatically focused page headings was removed while retaining focus for screen readers and visible indicators on interactive controls. A toast side accent found by the design detector was replaced with a restrained full border.

The shared shell and controls implement the selected visual system. The overview's actual metric strip, chart, filters and invoice table remain dependent on the integrated reporting backend. Current feature placeholders are deliberate and cannot be described as full mockup fidelity. The final reporting page must match the chosen composition using committed database records; never copy the preview's sample totals into production.

Source references: [Graphite Mint](graphite-mint.png), [Sage Commerce](sage-commerce.png). The Shopify-like task hierarchy was informed by [Shopify's visual-design guidance](https://shopify.dev/docs/apps/design/visual-design); this is an independent Cadentra interface, not an embedded Shopify app. Animation implementation follows [Motion's React accessibility guidance](https://motion.dev/docs/react-accessibility).

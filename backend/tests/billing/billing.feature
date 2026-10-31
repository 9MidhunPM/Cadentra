# Prepared acceptance scenarios; NOT RUN against application services.
Feature: Billing preserves money, historical policy and payment history
  Background:
    Given financial writes use the shared actor and business clock
    And all invoice amounts are calculated on the backend with Decimal

  @T08 @T14 @T15 @T16
  Scenario: Actual pricing service matches prepared decimal vectors
    When each case in contracts/billing-vectors.json and pricing_cases.json is calculated
    Then actual subtotal, discount, tax, total and per-line discounts match exactly
    And the subscription inputs contain exactly one flattened BASE line
    And each product unit_price already includes its quoted variant delta
    And the calculator does not add the base fee or variant delta again
    And every JSON money amount is a two-fractional-digit decimal string

  @T17
  Scenario Outline: Rule eligibility uses the eligible undiscounted charges
    Given a rule has <scope> scope
    When the eligible gross is <gross> and eligible product quantity is <quantity>
    And the minimum purchase is 100.00 and minimum quantity is 2
    Then minimum eligibility is <eligible>
    Examples:
      | scope        | gross  | quantity | eligible |
      | PRODUCTS     | 100.00 | 2        | true     |
      | PRODUCTS     | 99.99  | 2        | false    |
      | SUBSCRIPTION | 100.00 | 1        | false    |
    # BASE contributes to SUBSCRIPTION gross but never product quantity.

  @T17 @T18
  Scenario: Choose one maximum-benefit rule without stacking
    Given eligible rules offer fixed 15.00, percentage benefit 20.00 and fixed 20.00
    When billing selects a rule while protecting the global usage cap
    Then exactly one 20.00 benefit applies
    And its stable rule ID is the lower of the tied IDs
    And an exhausted rule is excluded after a locked recheck
    And a retried invoice consumes no extra redemption

  @T17 @T21 @T26
  Scenario: Catch-up selects retained policy by service date
    Given a tax or discount rule has distinct adjacent effective-dated revisions
    When an old due period is invoiced after the new revision becomes effective
    Then its rule revision and validity window are evaluated at period_start
    And a boundary date selects the new revision only from its inclusive start
    And expiry uses the exclusive end of the validity window
    And usage counts remain shared across discount revisions
    And neither catalog edits nor rule edits change an existing invoice snapshot

  @T21
  Scenario: Catch-up invoice grants payment terms from actual issuance
    Given a due period starts on 2026-10-01 with payment terms of 7 days
    And the injected Asia/Kolkata business clock is 2026-10-31
    When the period is first invoiced
    Then invoice_date is 2026-10-31 and due_date is 2026-11-07
    And period_start remains 2026-10-01
    And confirmation and matching replay preserve both invoice dates
    And the production run-due request cannot override the business clock

  @T22 @T23
  Scenario: Replay an exact settlement after the invoice has become paid
    Given a confirmed invoice totals 4970.16
    When payment 2000.00 with request key first is recorded
    Then balance is 2970.16 and status is CONFIRMED
    When payment 2970.16 with request key final is recorded
    Then balance is 0.00 and status is PAID
    When the normalized final payment payload is replayed with the same key
    Then the original payment is returned and exactly two payments remain
    When that key is reused with a different amount, date, method or note
    Then a conflict is returned without a new payment

  @T22 @T24
  Scenario Outline: Reject invalid payments without side effects
    Given the invoice status is <status> and its balance is 100.00
    When a payment with <input> is submitted
    Then it is rejected with no payment, audit-success or balance mutation
    Examples:
      | status    | input                         |
      | CONFIRMED | amount 0.00                   |
      | CONFIRMED | amount -0.01                  |
      | CONFIRMED | amount 100.01                 |
      | CONFIRMED | paid_on after business today  |
      | DRAFT     | amount 1.00                   |
      | CANCELLED | amount 1.00                   |

  @T22
  Scenario: Confirm an invoice fully discounted to zero
    Given a draft invoice totals 0.00
    When the invoice is confirmed
    Then its status is PAID and balance is 0.00
    And no payment record is invented

  @T25
  Scenario: Cancellation preserves period and discount history
    Given a draft or unpaid confirmed invoice has consumed one discount use
    When it is cancelled with a reason
    Then its status is CANCELLED and the reason is retained
    And its billing period and redemption remain durable
    And its discount usage is not restored
    And recurring billing cannot automatically replace that cancelled invoice
    And a paid or partially paid invoice cannot be cancelled

  @T05 @T27
  Scenario: Backend permissions apply independently of visible buttons
    Given a staff actor can read tax and discount rules
    When the actor attempts to create or revise either rule
    Then the backend returns 403 with no mutation
    And an unauthenticated invoice mutation returns 401
    And a mutation without valid CSRF and Origin is rejected

  @T27
  Scenario: Print and email preserve ownership and honest delivery state
    Given customer A and customer B own different invoices
    When A requests B's invoice or printable view through the portal service
    Then the result is 404 without cost data or private staff notes
    When invoice descriptions contain HTML markup
    Then the authorized printable view escapes that markup
    When staff sends an invoice with a request key
    Then HTTP returns 202 with an outbox status
    And a matching retry creates no extra invoice, payment or outbox intent
    And queued status does not claim external delivery

  @T27
  Scenario: Verify an actual invoice email reaches a controlled external inbox
    Given an authorized controlled mailbox and configured real SMTP provider
    And a persisted invoice with its recipient linked to that mailbox
    When the actual send operation is dispatched by the outbox worker
    Then the invoice email is observed in the controlled external inbox
    And its invoice number, recipient and amount match the persisted snapshot
    And evidence records the tested commit, send time and receipt result
    And private addresses, credentials and message content stay out of public artifacts
    # NOT RUN. SMTP acceptance or a local capture cannot pass this scenario.

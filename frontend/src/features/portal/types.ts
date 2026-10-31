export interface SubscriptionRecord {
  id: string;
  number: string;
  plan_id: string;
  state: string;
  start_date: string;
  end_date: string;
  currency: string;
  close_effective_on: string | null;
  revision: number;
}
export interface TaxMetadata {
  id: string;
  name: string;
  rate_percent: string;
}
export interface SubscriptionDetail extends SubscriptionRecord {
  prior_subscription_id: string | null;
  expired: boolean;
  recurring_subtotal: string;
  recurring_subtotal_basis: string;
  base_fee_taxes: TaxMetadata[];
  tax_preview_on: string;
  tax_preview_basis: string;
  payment_terms_days: number;
  quotation_valid_until?: string | null;
  plan_snapshot: {
    name?: string;
    cadence?: string;
    base_fee?: string;
    currency?: string;
  };
  lines: {
    id: string;
    description: string;
    quantity: number;
    unit_price: string;
    line_total: string;
    taxes: TaxMetadata[];
  }[];
  next_billing_date?: string | null;
  paused?: boolean;
  pause_interval: { starts_on: string; ends_on: string | null } | null;
  pause_effective_on: string | null;
  resume_effective_on: string | null;
  allowed_actions?: string[];
  invoice_references: { id: string; number: string; status: string }[];
}
export interface InvoiceRecord {
  id: string;
  number: string;
  subscription_id: string;
  status: string;
  collection_status: string;
  currency: string;
  invoice_date: string;
  due_date: string;
  period_start: string;
  period_end: string;
  total: string;
  paid_amount: string;
  balance_due: string;
  overdue: boolean;
}
export interface InvoiceDetail extends InvoiceRecord {
  subtotal: string;
  discount_total: string;
  tax_total: string;
  lines: {
    id: string;
    stable_line_key: string;
    description: string;
    quantity: number;
    unit_price: string;
    gross: string;
    discount: string;
    taxable_amount: string;
    tax_total: string;
    total: string;
    taxes?: { name: string; rate_percent: string; amount: string }[];
  }[];
  payments: { id: string; method: string; amount: string; paid_on: string }[];
  seller_snapshot?: {
    name?: string;
    address?: unknown;
    billing_address?: unknown;
  };
  customer_snapshot?: {
    display_name?: string;
    email?: string;
    company_name?: string;
    billing_address?: unknown;
  };
}
export interface CustomerProfile {
  id: string;
  display_name: string;
  email: string;
  company_name: string | null;
  billing_address: {
    line1?: string;
    line2?: string;
    city?: string;
    state?: string;
    postal_code?: string;
    country?: string;
  };
}

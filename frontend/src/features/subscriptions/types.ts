export interface TaxRuleReference { id: string; name: string; rate_percent: string }
export interface LineInput { product_id: string; variant_id?: string; quantity: number }
export interface Line extends Omit<LineInput, 'variant_id'> { variant_id?: string | null; id?: string; description?: string; unit_price?: string; line_total?: string; taxes?: TaxRuleReference[] }
export interface Plan { id: string; name: string; cadence: string; base_fee: string; min_quantity: number; available_from?: string; available_until?: string | null }
export interface Customer { id: string; display_name: string }
export interface Variant { id: string; attribute_name: string; attribute_value: string; price_delta: string; active: boolean }
export interface Product { id: string; name: string; active: boolean; variants?: Variant[] }
export interface Template { id: string; name: string; plan_id: string; valid_days: number; lines: Line[] }
export interface Subscription {
  id: string; number: string; customer_id: string; customer_name?: string; plan_id: string;
  state: string; start_date: string; end_date: string; payment_terms_days: number;
  currency: string; quotation_valid_days?: number; quotation_valid_until?: string | null; revision: number;
  plan_snapshot: Partial<Plan> & { allow_pause?: boolean; allow_early_close?: boolean; allow_renew?: boolean; auto_close?: boolean };
  lines: Line[]; allowed_actions: string[]; next_billing_date?: string | null;
  paused?: boolean; expired?: boolean; pause_interval?: { starts_on: string; ends_on: string | null } | null;
  pause_effective_on?: string | null; resume_effective_on?: string | null; close_effective_on?: string | null;
  base_fee_taxes?: TaxRuleReference[]; tax_preview_on?: string; tax_preview_basis?: string; recurring_subtotal?: string; invoice_references?: { id: string; number: string; status: string }[];
}

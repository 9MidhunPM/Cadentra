export interface Customer {
  id: string;
  display_name: string;
  email: string;
  company_name: string | null;
  billing_address: Record<string, unknown>;
}
export interface Product {
  id: string;
  name: string;
  product_type: string;
  sales_price: string;
  cost_price: string;
  notes: string | null;
  active: boolean;
}
export interface Variant {
  id: string;
  attribute_name: string;
  attribute_value: string;
  price_delta: string;
  active: boolean;
}
export interface ProductDetail extends Product {
  variants: Variant[];
}
export interface Plan {
  id: string;
  name: string;
  base_fee: string;
  currency: string;
  cadence: string;
  min_quantity: number;
  available_from: string;
  available_until: string | null;
  allow_pause: boolean;
  allow_early_close: boolean;
  allow_renew: boolean;
  auto_close: boolean;
  tax_rule_ids: string[];
}

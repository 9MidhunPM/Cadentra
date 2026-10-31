/** Monetary values stay decimal strings; authoritative arithmetic belongs to the API. */
export type Money = string;
export type Role = 'ADMIN' | 'STAFF' | 'CUSTOMER';
export interface Actor {
  id: string;
  name: string;
  role: Role;
  customer_id: string | null;
}
export interface ResourceResponse<T> { data: T }
export interface ListResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface SessionPayload { actor: Actor; csrf_token: string }

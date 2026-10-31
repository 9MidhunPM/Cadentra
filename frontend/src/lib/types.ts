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
export type DevToolsStatus = { enabled: boolean; unlocked: false } | {
  enabled: true;
  unlocked: true;
  dev_csrf_token: string;
  expires_at: string;
  operator: { id: string; name: string };
  target: Actor;
};
export interface SessionPayload { actor: Actor; csrf_token: string; dev_tools?: DevToolsStatus }

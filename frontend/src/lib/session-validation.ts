import type { Actor, DevToolsStatus, SessionPayload } from './types';

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
export function validActor(value: unknown): value is Actor {
  return record(value) && typeof value.id === 'string' && value.id.length > 0 && typeof value.name === 'string'
    && typeof value.role === 'string' && ['ADMIN', 'STAFF', 'CUSTOMER'].includes(value.role)
    && (value.customer_id === null || typeof value.customer_id === 'string')
    && (value.role !== 'CUSTOMER' || typeof value.customer_id === 'string' && value.customer_id.length > 0);
}
export function validDevToolsStatus(value: unknown): value is DevToolsStatus {
  if (!record(value) || typeof value.enabled !== 'boolean' || typeof value.unlocked !== 'boolean') return false;
  if (!value.unlocked) return true;
  return value.enabled && typeof value.dev_csrf_token === 'string' && value.dev_csrf_token.length > 0
    && typeof value.expires_at === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value.expires_at) && Number.isFinite(Date.parse(value.expires_at))
    && record(value.operator) && typeof value.operator.id === 'string' && value.operator.id.length > 0 && typeof value.operator.name === 'string'
    && validActor(value.target);
}
export function validSessionPayload(value: unknown): value is SessionPayload {
  return record(value) && validActor(value.actor) && typeof value.csrf_token === 'string' && value.csrf_token.length > 0
    && (value.dev_tools === undefined || validDevToolsStatus(value.dev_tools)
      && (!value.dev_tools.unlocked || value.dev_tools.target.id === value.actor.id
        && value.dev_tools.target.role === value.actor.role && value.dev_tools.target.customer_id === value.actor.customer_id));
}

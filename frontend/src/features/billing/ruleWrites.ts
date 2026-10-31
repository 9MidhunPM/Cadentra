import { useSyncExternalStore } from 'react';

export type RuleKind = 'tax' | 'discount';
export type RuleWriteState = 'idle' | 'pending' | 'uncertain' | 'refresh';
// Runtime-wide coordination only: no payloads, identifiers or credentials.
const writes: Record<RuleKind, { state: RuleWriteState; version: number }> = {
  tax: { state: 'idle', version: 0 }, discount: { state: 'idle', version: 0 },
};
const listeners = new Set<() => void>();
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function getRuleWrite(kind: RuleKind) { return writes[kind]; }
export function setRuleWrite(kind: RuleKind, state: RuleWriteState) {
  writes[kind] = { state, version: writes[kind].version + 1 };
  listeners.forEach(listener => listener());
}
export function beginRuleWrite(kind: RuleKind): boolean {
  if (writes[kind].state !== 'idle') return false;
  setRuleWrite(kind, 'pending');
  return true;
}
export function completeRuleRead(kind: RuleKind, version: number): boolean {
  if (writes[kind].version !== version || writes[kind].state === 'pending') return false;
  setRuleWrite(kind, 'idle');
  return true;
}
export function useRuleWriteState(kind: RuleKind) {
  return useSyncExternalStore(subscribe, () => writes[kind].state);
}

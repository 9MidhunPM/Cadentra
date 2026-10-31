/** Cross-tab signals carry no account information, credentials, CSRF tokens or grant authority. */
export const AUTH_EVENT_KEY = 'cadentra:auth-change';
type AuthEvent = { event: 'changed'; timestamp: number };
const listeners = new Set<() => void>();
let channel: BroadcastChannel | null = null;

export const authNavigation = {
  reload: () => window.location.reload(),
  assign: (path: '/dev' | '/app' | '/sign-in') => window.location.assign(path),
};
function validEvent(value: unknown): value is AuthEvent {
  return value !== null && typeof value === 'object' && 'event' in value && value.event === 'changed'
    && 'timestamp' in value && typeof value.timestamp === 'number' && Number.isFinite(value.timestamp);
}
export function notifyAuthChange() {
  if (typeof window === 'undefined') return;
  const event: AuthEvent = { event: 'changed', timestamp: Date.now() };
  try {
    if (channel) channel.postMessage(event);
    else if (typeof window.BroadcastChannel === 'function') {
      const sender = new window.BroadcastChannel(AUTH_EVENT_KEY);
      sender.postMessage(event); sender.close();
    }
  } catch { /* A restricted browser can still use the storage-event fallback. */ }
  try {
    // Removing the marker ensures a second change in the same millisecond still fires.
    window.localStorage.setItem(AUTH_EVENT_KEY, JSON.stringify(event));
    window.localStorage.removeItem(AUTH_EVENT_KEY);
  } catch {
    // Browser privacy policies may block storage; BroadcastChannel remains available.
  }
}
export function subscribeAuthChanges(listener: () => void) {
  listeners.add(listener);
  if (!channel && typeof window.BroadcastChannel === 'function') {
    try {
      channel = new window.BroadcastChannel(AUTH_EVENT_KEY);
      channel.onmessage = event => { if (validEvent(event.data)) listeners.forEach(notify => notify()); };
    } catch { /* Storage events remain available when channels are restricted. */ }
  }
  const storage = (event: StorageEvent) => {
    if (event.key !== AUTH_EVENT_KEY || !event.newValue) return;
    try { if (validEvent(JSON.parse(event.newValue))) listener(); }
    catch { /* Ignore unrelated/malformed storage events; they carry no session authority. */ }
  };
  window.addEventListener('storage', storage);
  return () => {
    listeners.delete(listener); window.removeEventListener('storage', storage);
    if (!listeners.size) { channel?.close(); channel = null; }
  };
}

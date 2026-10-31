import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { apiClient, ApiError, isAbortError } from './api';
import type { Actor, ResourceResponse, SessionPayload } from './types';

export type SessionStatus = 'loading' | 'authenticated' | 'anonymous' | 'error';
interface SessionState { status: SessionStatus; actor: Actor | null; error: unknown }
interface SessionContextValue extends SessionState {
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}
const SessionContext = createContext<SessionContextValue | null>(null);
const empty: SessionState = { status: 'loading', actor: null, error: null };

function validSession(value: unknown): value is SessionPayload {
  if (!value || typeof value !== 'object') return false;
  const session = value as Partial<SessionPayload>;
  const actor = session.actor;
  return typeof session.csrf_token === 'string' && session.csrf_token.length > 0 && !!actor &&
    typeof actor.id === 'string' && typeof actor.name === 'string' &&
    ['ADMIN', 'STAFF', 'CUSTOMER'].includes(actor.role) &&
    (actor.customer_id === null || typeof actor.customer_id === 'string') &&
    (actor.role !== 'CUSTOMER' || typeof actor.customer_id === 'string');
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(empty);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const serial = ++generation.current;
    setState(empty);
    try {
      const result = await apiClient.request<ResourceResponse<SessionPayload>>('/auth/session', { signal: abort.signal });
      if (abort.signal.aborted || serial !== generation.current) return;
      if (!validSession(result.data)) throw new ApiError(200, 'INVALID_SESSION', 'The server returned an invalid session.');
      apiClient.setCsrfToken(result.data.csrf_token);
      setState({ status: 'authenticated', actor: result.data.actor, error: null });
    } catch (error) {
      if (abort.signal.aborted || serial !== generation.current || isAbortError(error)) return;
      apiClient.setCsrfToken(null);
      if (error instanceof ApiError && error.status === 401) {
        setState({ status: 'anonymous', actor: null, error: null });
      } else {
        setState({ status: 'error', actor: null, error });
      }
    }
  }, []);

  const logout = useCallback(async () => {
    controller.current?.abort();
    const serial = ++generation.current;
    try {
      await apiClient.request<void>('/auth/logout', { method: 'POST' });
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    if (serial !== generation.current) return;
    apiClient.setCsrfToken(null);
    setState({ status: 'anonymous', actor: null, error: null });
  }, []);

  useEffect(() => {
    const unsubscribe = apiClient.onUnauthorized(() => {
      generation.current += 1;
      controller.current?.abort();
      setState({ status: 'anonymous', actor: null, error: null });
    });
    void refresh();
    return () => {
      unsubscribe();
      generation.current += 1;
      controller.current?.abort();
      apiClient.setCsrfToken(null);
    };
  }, [refresh]);

  return <SessionContext.Provider value={{ ...state, refresh, logout }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}

// @vitest-environment jsdom
import { act, cleanup, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SessionProvider, useSession } from './session';
import { apiClient } from './api';
import { AUTH_EVENT_KEY, authNavigation } from './auth-events';

const actor = { id: 'actor-1', name: 'Customer One', role: 'CUSTOMER', customer_id: 'customer-1' };
function Probe() {
  const session = useSession();
  return <><span data-testid="status">{session.status}</span><span>{session.actor?.name}</span>
    <button onClick={() => void session.refresh()}>Refresh session</button>
    <button onClick={() => void session.logout()}>Log out</button></>;
}
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('server session state', () => {
  it('clears actor/grant state and reloads on a cross-tab account change, ignoring an older refresh', async () => {
    const reload = vi.spyOn(authNavigation, 'reload').mockImplementation(() => {});
    let resolveRefresh!: (value: Response) => void;
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveRefresh = resolve; }));
    vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('authenticated'));
    let refreshing!: Promise<void>;
    await act(async () => { refreshing = result.current.refresh(); });
    await act(async () => { window.dispatchEvent(new StorageEvent('storage', { key: AUTH_EVENT_KEY, newValue: '{"event":"changed","timestamp":1}' })); });
    expect(result.current.actor).toBeNull(); expect(result.current.devTools).toBeNull(); expect(reload).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[1][1]?.signal?.aborted).toBe(true);
    await act(async () => { resolveRefresh(response({ data: { actor, csrf_token: 'old-csrf' } })); await refreshing; });
    expect(result.current.actor).toBeNull();
  });

  it('rejects mismatched role-testing target metadata instead of exposing the session', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response({ data: { actor, csrf_token: 'csrf', dev_tools: {
      enabled: true, unlocked: true, dev_csrf_token: 'private-dev-csrf', expires_at: '2099-01-01T00:00:00Z',
      operator: { id: 'admin-1', name: 'Operator' }, target: { ...actor, id: 'another-user' },
    } } })));
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.actor).toBeNull(); expect(result.current.devTools).toBeNull();
  });

  it.each([
    { ...actor, role: 'STAFF', customer_id: null },
    { ...actor, customer_id: 'another-customer' },
  ])('rejects a same-ID role-testing target with changed role or customer scope', async target => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response({ data: { actor, csrf_token: 'csrf', dev_tools: {
      enabled: true, unlocked: true, dev_csrf_token: 'private-dev-csrf', expires_at: '2099-01-01T00:00:00Z',
      operator: { id: 'admin-1', name: 'Operator' }, target,
    } } })));
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.actor).toBeNull(); expect(result.current.devTools).toBeNull();
  });

  it('rejects role-testing authority with an empty operator ID', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response({ data: { actor, csrf_token: 'csrf', dev_tools: {
      enabled: true, unlocked: true, dev_csrf_token: 'private-dev-csrf', expires_at: '2099-01-01T00:00:00Z',
      operator: { id: '', name: 'Operator' }, target: actor,
    } } })));
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.actor).toBeNull(); expect(result.current.devTools).toBeNull();
  });
  it('loads the real session and invalidates it on logout', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetcher);
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'));
    expect(screen.getByText('Customer One')).toBeTruthy();
    await act(async () => screen.getByText('Log out').click());
    expect(screen.getByTestId('status').textContent).toBe('anonymous');
    expect(fetcher.mock.calls[1][0]).toBe('/api/v1/auth/logout');
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).get('X-CSRF-Token')).toBe('csrf');
  });

  it('treats only 401 as anonymous', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response({ error: { code: 'UNAUTHENTICATED' } }, 401)));
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('anonymous'));
  });

  it('shows connection failure as error and permits an explicit refresh', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }));
    vi.stubGlobal('fetch', fetcher);
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('error'));
    await act(async () => screen.getByText('Refresh session').click());
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'));
  });

  it('rejects malformed session data instead of granting access', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(response({ data: { actor: { ...actor, customer_id: null }, csrf_token: 'csrf' } })));
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('error'));
  });

  it('clears the displayed actor when a protected feature request returns 401', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockResolvedValueOnce(response({ error: { code: 'UNAUTHENTICATED' } }, 401));
    vi.stubGlobal('fetch', fetcher);
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'));
    await act(async () => {
      await expect(apiClient.request('/portal/subscriptions/one/pause', { method: 'POST' })).rejects.toMatchObject({ status: 401 });
    });
    expect(screen.getByTestId('status').textContent).toBe('anonymous');
    expect(screen.queryByText('Customer One')).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(['/auth/login', '/auth/signup', '/auth/password-reset/request', '/auth/password-reset/confirm'])('does not expire the active session on public auth failure at %s', async path => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockResolvedValueOnce(response({ error: { code: 'INVALID_CREDENTIALS' } }, 401))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetcher);
    render(<SessionProvider><Probe /></SessionProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'));
    await act(async () => {
      await expect(apiClient.request(path, { method: 'POST' })).rejects.toMatchObject({ status: 401 });
    });
    expect(screen.getByTestId('status').textContent).toBe('authenticated');
    await act(async () => screen.getByText('Log out').click());
    expect(new Headers(fetcher.mock.calls[2][1]?.headers).get('X-CSRF-Token')).toBe('csrf');
  });

  it('deduplicates logout and suppresses refresh until logout finishes', async () => {
    let resolveLogout!: (value: Response) => void;
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveLogout = resolve; }));
    vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('authenticated'));
    let pending!: Promise<void>;
    await act(async () => {
      pending = result.current.logout();
      expect(result.current.logout()).toBe(pending);
      await result.current.refresh();
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    await act(async () => {
      resolveLogout(new Response(null, { status: 204 }));
      await pending;
    });
    expect(result.current.status).toBe('anonymous');
    expect(result.current.actor).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('retains the actor after failed logout and allows an explicit refresh and logout retry', async () => {
    let resolveLogout!: (value: Response) => void;
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveLogout = resolve; }))
      .mockResolvedValueOnce(response({ data: { actor, csrf_token: 'new-csrf' } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('authenticated'));
    let pending!: Promise<void>;
    await act(async () => {
      pending = result.current.logout();
      await result.current.refresh();
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    await act(async () => {
      resolveLogout(response({ error: { code: 'UNAVAILABLE' } }, 503));
      await expect(pending).rejects.toMatchObject({ status: 503 });
    });
    expect(result.current.status).toBe('authenticated');
    expect(result.current.actor?.id).toBe(actor.id);
    await act(async () => result.current.refresh());
    expect(fetcher.mock.calls[2][0]).toBe('/api/v1/auth/session');
    await act(async () => result.current.logout());
    expect(result.current.status).toBe('anonymous');
    expect(new Headers(fetcher.mock.calls[3][1]?.headers).get('X-CSRF-Token')).toBe('new-csrf');
    expect(fetcher).toHaveBeenCalledTimes(4);
  });

  it('does not restore an actor from an older refresh completing after logout', async () => {
    let resolveRefresh!: (value: Response) => void;
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveRefresh = resolve; }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('authenticated'));
    let pendingRefresh!: Promise<void>;
    await act(async () => { pendingRefresh = result.current.refresh(); });
    await act(async () => result.current.logout());
    await act(async () => {
      resolveRefresh(response({ data: { actor, csrf_token: 'stale-csrf' } }));
      await pendingRefresh;
    });
    expect(result.current.status).toBe('anonymous');
    expect(result.current.actor).toBeNull();
  });

  it('offers recovery when logout cancels a refresh and then fails', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(response({ data: { actor, csrf_token: 'csrf' } }))
      .mockImplementationOnce(() => new Promise(() => {}))
      .mockResolvedValueOnce(response({ error: { code: 'UNAVAILABLE' } }, 503))
      .mockResolvedValueOnce(response({ data: { actor, csrf_token: 'recovered' } }));
    vi.stubGlobal('fetch', fetcher);
    const { result } = renderHook(useSession, { wrapper: SessionProvider });
    await waitFor(() => expect(result.current.status).toBe('authenticated'));
    await act(async () => { void result.current.refresh(); });
    expect(result.current.status).toBe('loading');
    await act(async () => { await expect(result.current.logout()).rejects.toMatchObject({ status: 503 }); });
    expect(result.current.status).toBe('error');
    await act(async () => result.current.refresh());
    expect(result.current.status).toBe('authenticated');
  });

  it('aborts its pending session request on unmount', () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(() => new Promise(() => {}));
    vi.stubGlobal('fetch', fetcher);
    const { unmount } = render(<SessionProvider><Probe /></SessionProvider>);
    const signal = fetcher.mock.calls[0][1]?.signal;
    unmount();
    expect(signal?.aborted).toBe(true);
  });
});

// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SessionProvider, useSession } from './session';
import { apiClient } from './api';

const actor = { id: 'actor-1', name: 'Customer One', role: 'CUSTOMER', customer_id: 'customer-1' };
function Probe() {
  const session = useSession();
  return <><span data-testid="status">{session.status}</span><span>{session.actor?.name}</span>
    <button onClick={() => void session.refresh()}>Refresh session</button>
    <button onClick={() => void session.logout()}>Log out</button></>;
}
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('server session state', () => {
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

  it('aborts its pending session request on unmount', () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(() => new Promise(() => {}));
    vi.stubGlobal('fetch', fetcher);
    const { unmount } = render(<SessionProvider><Probe /></SessionProvider>);
    const signal = fetcher.mock.calls[0][1]?.signal;
    unmount();
    expect(signal?.aborted).toBe(true);
  });
});

import { describe, expect, it, vi } from 'vitest';
import { ApiError, createApiClient, getErrorMessage } from './api';

const jsonResponse = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('same-origin API transport', () => {
  it('preserves resource/list envelopes and decimal strings', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse({ data: { total: '4970.16' } }))
      .mockResolvedValueOnce(jsonResponse({ items: [], total: 0, page: 1, page_size: 25 }));
    const client = createApiClient(fetcher);
    await expect(client.request('/invoices/one')).resolves.toEqual({ data: { total: '4970.16' } });
    await expect(client.request('/invoices?page=1')).resolves.toEqual({ items: [], total: 0, page: 1, page_size: 25 });
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/invoices/one');
    expect(fetcher.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin', redirect: 'error' });
  });

  it('adds the current CSRF token only to mutations and sends JSON once', async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => jsonResponse({ data: {} }));
    const client = createApiClient(fetcher);
    client.setCsrfToken('session-token');
    await client.request('/auth/session');
    await client.request('/invoices/one/payments', { method: 'POST', json: { amount: '2000.00' } });
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).has('X-CSRF-Token')).toBe(false);
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).get('X-CSRF-Token')).toBe('session-token');
    expect(fetcher.mock.calls[1][1]?.body).toBe('{"amount":"2000.00"}');
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(['https://evil.invalid/steal', '//evil.invalid', '/../../steal', '/%2e%2e/steal', '/safe\\evil', '/safe#fragment', '/x/./y'])('rejects unsafe path %s before sending credentials', async path => {
    const fetcher = vi.fn<typeof fetch>();
    await expect(createApiClient(fetcher).request(path)).rejects.toMatchObject({ code: 'INVALID_API_PATH' });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([401, 403, 404, 409, 422])('retains API error details for HTTP %s', async status => {
    const client = createApiClient(vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ error: {
      code: 'DOMAIN_ERROR', message: 'Explain the problem.', fields: { amount: 'Invalid amount' }, request_id: 'req-1',
    } }, status)));
    await expect(client.request('/invoices')).rejects.toMatchObject({ status, code: 'DOMAIN_ERROR', message: 'Explain the problem.', fields: { amount: 'Invalid amount' }, requestId: 'req-1' });
  });

  it('clears stale CSRF after unauthorized response', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse({}, 401)).mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient(fetcher);
    client.setCsrfToken('expired');
    await expect(client.request('/auth/session')).rejects.toBeInstanceOf(ApiError);
    await client.request('/auth/logout', { method: 'POST' });
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).has('X-CSRF-Token')).toBe(false);
  });

  it('does not expire a newer session when an old request returns 401', async () => {
    let resolveResponse!: (value: Response) => void;
    const fetcher = vi.fn<typeof fetch>().mockImplementationOnce(() => new Promise(resolve => { resolveResponse = resolve; }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient(fetcher);
    const unauthorized = vi.fn();
    client.onUnauthorized(unauthorized);
    client.setCsrfToken('old');
    const pending = client.request('/invoices');
    client.setCsrfToken('new');
    resolveResponse(jsonResponse({}, 401));
    await expect(pending).rejects.toMatchObject({ status: 401 });
    expect(unauthorized).not.toHaveBeenCalled();
    await client.request('/auth/logout', { method: 'POST' });
    expect(new Headers(fetcher.mock.calls[1][1]?.headers).get('X-CSRF-Token')).toBe('new');
  });

  it('does not notify session expiry for an aborted request', async () => {
    const abort = new AbortController();
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => {
      abort.abort();
      return jsonResponse({}, 401);
    });
    const client = createApiClient(fetcher);
    const unauthorized = vi.fn();
    client.onUnauthorized(unauthorized);
    await expect(client.request('/invoices', { signal: abort.signal })).rejects.toMatchObject({ name: 'AbortError' });
    expect(unauthorized).not.toHaveBeenCalled();
  });

  it('distinguishes connection failure from authentication failure and does not retry', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(createApiClient(fetcher).request('/invoices', { method: 'POST' })).rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('preserves cancellation without inventing a network error', async () => {
    const error = new DOMException('Cancelled', 'AbortError');
    await expect(createApiClient(vi.fn<typeof fetch>().mockRejectedValue(error)).request('/auth/session')).rejects.toBe(error);
  });

  it('handles expected no-body responses', async () => {
    const client = createApiClient(vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(client.request<void>('/auth/logout', { method: 'POST' })).resolves.toBeUndefined();
  });

  it.each(['<html>Proxy failed</html>', '{}', 'null', '[]'])('rejects malformed success response %s', async body => {
    await expect(createApiClient(vi.fn<typeof fetch>().mockResolvedValue(new Response(body))).request('/auth/session')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });

  it.each([
    { items: [] },
    { items: [], total: -1, page: 1, page_size: 25 },
    { items: [], total: 0.5, page: 1, page_size: 25 },
    { items: [], total: Number.MAX_SAFE_INTEGER + 1, page: 1, page_size: 25 },
    { items: [], total: 0, page: 0, page_size: 25 },
    { items: [], total: 0, page: '1', page_size: 25 },
    { items: [], total: 0, page: 1, page_size: 0 },
    { items: [], total: 0, page: 1, page_size: 101 },
    { items: [], total: 0, page: 1, page_size: 2.5 },
  ])('rejects invalid pagination metadata: %j', async payload => {
    const client = createApiClient(vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload)));
    await expect(client.request('/invoices')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });

  it('accepts pagination boundaries without requiring a nonempty result', async () => {
    const payload = { items: [], total: 0, page: 1, page_size: 100 };
    await expect(createApiClient(vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload))).request('/invoices')).resolves.toEqual(payload);
  });

  it('reports local JSON encoding errors without sending or retrying a request', async () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    const fetcher = vi.fn<typeof fetch>();
    const client = createApiClient(fetcher);
    for (const json of [circular, { amount: 1n }, () => {}]) {
      await expect(client.request('/invoices', { method: 'POST', json })).rejects.toMatchObject({ status: 0, code: 'INVALID_REQUEST' });
    }
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('does not display HTML proxy responses or unknown exception details', async () => {
    const client = createApiClient(vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>private proxy internals</html>', { status: 503 })));
    await expect(client.request('/auth/session')).rejects.toMatchObject({ status: 503, message: 'The server could not complete this request.' });
    expect(getErrorMessage(new Error('secret'))).not.toContain('secret');
  });
});

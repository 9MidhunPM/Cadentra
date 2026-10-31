export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, unknown>;
  readonly requestId?: string;

  constructor(status: number, code: string, message: string, fields: Record<string, unknown> = {}, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.requestId = requestId;
  }
}

const statusMessages: Record<number, string> = {
  401: 'Your session has ended. Sign in again.',
  403: 'You do not have permission to perform this action.',
  404: 'This record is unavailable.',
  409: 'This action conflicts with the current record. Refresh and try again.',
  422: 'Check the highlighted fields and try again.',
};

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return 'Something went wrong. Please try again.';
}

export function isAbortError(error: unknown): boolean {
  return typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError';
}

export interface RequestOptions {
  method?: 'GET' | 'HEAD' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  json?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** One transport for same-origin /api/v1 requests. Never retries a mutation. */
export function createApiClient(fetcher: typeof fetch = (...args) => fetch(...args)) {
  let csrfToken: string | null = null;
  let sessionVersion = 0;
  const unauthorizedListeners = new Set<() => void>();
  return {
    setCsrfToken(token: string | null) { csrfToken = token; sessionVersion += 1; },
    onUnauthorized(listener: () => void) {
      unauthorizedListeners.add(listener);
      return () => { unauthorizedListeners.delete(listener); };
    },
    async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
      // Reject absolute URLs, protocol-relative URLs, backslashes, fragments and dot
      // segments before browser URL normalization can escape the API prefix.
      if (!path.startsWith('/') || path.startsWith('//') || /[\\#\s]/.test(path)) {
        throw new ApiError(0, 'INVALID_API_PATH', 'Use a path relative to the API.');
      }
      let decoded: string;
      try { decoded = decodeURIComponent(path.split('?')[0]); }
      catch { throw new ApiError(0, 'INVALID_API_PATH', 'Use a valid API path.'); }
      if (decoded.includes('\\') || decoded.split('/').some(segment => segment === '.' || segment === '..')) {
        throw new ApiError(0, 'INVALID_API_PATH', 'Use a path relative to the API.');
      }
      const requestSessionVersion = sessionVersion;
      const publicAuth = ['/auth/login', '/auth/signup', '/auth/password-reset/request', '/auth/password-reset/confirm'].includes(decoded.replace(/\/$/, ''));
      const method = options.method ?? 'GET';
      const headers = new Headers(options.headers);
      headers.set('Accept', 'application/json');
      headers.delete('X-CSRF-Token');
      if (options.json !== undefined) headers.set('Content-Type', 'application/json');
      if (csrfToken && method !== 'GET' && method !== 'HEAD') headers.set('X-CSRF-Token', csrfToken);
      let body: string | undefined;
      if (options.json !== undefined) {
        try {
          body = JSON.stringify(options.json);
          if (body === undefined) throw new TypeError('Not JSON serializable');
        } catch {
          throw new ApiError(0, 'INVALID_REQUEST', 'The request could not be encoded as JSON.');
        }
      }
      let response: Response;
      try {
        response = await fetcher(`/api/v1${path}`, {
          method, headers, credentials: 'same-origin', redirect: 'error',
          body,
          signal: options.signal,
        });
      } catch (error) {
        if (isAbortError(error) || options.signal?.aborted) throw error;
        throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.');
      }
      options.signal?.throwIfAborted();
      if (response.status === 401 && !publicAuth && requestSessionVersion === sessionVersion) {
        csrfToken = null;
        sessionVersion += 1;
        for (const listener of unauthorizedListeners) listener();
      }
      if (response.ok && (response.status === 204 || response.status === 205 || method === 'HEAD')) return undefined as T;
      let payload: unknown;
      try { payload = await response.json(); }
      catch (error) {
        if (isAbortError(error) || options.signal?.aborted) throw error;
        throw new ApiError(response.status, response.ok ? 'INVALID_RESPONSE' : `HTTP_${response.status}`,
          response.ok ? 'The server returned an unreadable response.' : statusMessages[response.status] ?? 'The server could not complete this request.');
      }
      if (!response.ok) {
        const details = isRecord(payload) && isRecord(payload.error) ? payload.error : {};
        throw new ApiError(response.status,
          typeof details.code === 'string' ? details.code : `HTTP_${response.status}`,
          typeof details.message === 'string' ? details.message : statusMessages[response.status] ?? 'The server could not complete this request.',
          isRecord(details.fields) ? details.fields : {},
          typeof details.request_id === 'string' ? details.request_id : undefined);
      }
      const validList = isRecord(payload) && Array.isArray(payload.items) &&
        Number.isSafeInteger(payload.total) && (payload.total as number) >= 0 &&
        Number.isSafeInteger(payload.page) && (payload.page as number) >= 1 &&
        Number.isSafeInteger(payload.page_size) && (payload.page_size as number) >= 1 && (payload.page_size as number) <= 100;
      if (!isRecord(payload) || (!('data' in payload) && !validList)) {
        throw new ApiError(response.status, 'INVALID_RESPONSE', 'The server returned an unexpected response.');
      }
      return payload as T;
    },
  };
}

export const apiClient = createApiClient();

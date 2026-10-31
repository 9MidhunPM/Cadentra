/** Required-response rules shared by the benchmark and its transport regression tests. */
export interface ApiExpectation<T> {
  path: string
  status?: number
  html?: boolean
  validate: (payload: T) => void
}
interface BodyResponse {
  status(): number
  text(): Promise<string>
  json(): Promise<unknown>
}
export interface BrowserResponse extends BodyResponse {
  url(): string
  request(): { method(): string; failure(): { errorText: string } | null }
  finished(): Promise<Error | null>
}
export const confirmedAbort = (message: string) => /ERR_ABORTED|cancelled|canceled|NS_BINDING_ABORTED/i.test(message)

export function anonymousSession401(response: BrowserResponse, anonymous: boolean, origin: string) {
  const url = new URL(response.url())
  return anonymous && url.origin === origin && url.pathname === '/api/v1/auth/session'
    && response.request().method() === 'GET' && response.status() === 401
}

/** Independent API measurements always consume and validate the complete body, including anonymous 401s. */
export async function validateApiResponse<T>(response: BodyResponse, api: ApiExpectation<T>) {
  if (response.status() !== (api.status ?? 200)) {
    throw new Error(`Required API ${api.path}: HTTP ${response.status()}, expected ${api.status ?? 200}`)
  }
  const payload = api.html ? await response.text() : await response.json()
  api.validate(payload as T)
}

export async function requiredBrowserResponse<T>(response: BrowserResponse, api: ApiExpectation<T>, origin: string, anonymous: boolean) {
  const actual = new URL(response.url()), wanted = new URL(api.path, origin)
  if (response.request().method() !== 'GET' || actual.origin !== wanted.origin || actual.pathname !== wanted.pathname
    || ![...wanted.searchParams].every(([key, value]) => actual.searchParams.get(key) === value)) return false
  // The session provider can abort this request when its 401 headers establish
  // anonymous state. Form readiness is checked separately by the route;
  // waiting for this browser body's completion can never establish that state.
  if (api.status === 401 && anonymousSession401(response, anonymous, origin)) return true
  const failure = await response.finished()
  if (failure) {
    if (confirmedAbort(response.request().failure()?.errorText || '')) return false
    throw failure
  }
  await validateApiResponse(response, api)
  return true
}

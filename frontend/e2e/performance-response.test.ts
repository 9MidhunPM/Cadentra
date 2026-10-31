import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { ApiExpectation, BrowserResponse } from './performance-response'

// Native Node needs the .ts URL; keep the application's bundler import rules unchanged.
const { requiredBrowserResponse, validateApiResponse }: typeof import('./performance-response') = await import(new URL('./performance-response.ts', import.meta.url).href)

const origin = 'http://127.0.0.1:8080'
const session: ApiExpectation<unknown> = { path: '/api/v1/auth/session', status: 401,
  validate: payload => assert.deepEqual(payload, { error: { code: 'UNAUTHENTICATED' } }) }
function response(overrides: Partial<BrowserResponse> = {}): BrowserResponse {
  return { url: () => `${origin}/api/v1/auth/session`, request: () => ({ method: () => 'GET', failure: () => null }),
    status: () => 401, finished: async () => null, json: async () => ({ error: { code: 'UNAUTHENTICATED' } }),
    text: async () => '', ...overrides }
}

test('anonymous session 401 resolves on headers even when finished and body never settle', async () => {
  let bodyOrFinishedRead = false
  const never = () => { bodyOrFinishedRead = true; return new Promise<never>(() => {}) }
  assert.equal(await requiredBrowserResponse(response({ finished: never, json: never, text: never }), session, origin, true), true)
  assert.equal(bodyOrFinishedRead, false)
})
test('anonymous non-session 401 still consumes and validates its body', async () => {
  let consumed = false
  const api = { ...session, path: '/api/v1/invoices', validate: () => { consumed = true } }
  assert.equal(await requiredBrowserResponse(response({ url: () => `${origin}${api.path}` }), api, origin, true), true)
  assert.equal(consumed, true)
})
test('authenticated session 401 cannot use the anonymous exception', async () => {
  await assert.rejects(requiredBrowserResponse(response({ json: async () => { throw new Error('incomplete JSON') } }), session, origin, false), /incomplete JSON/)
})
test('business success waits for the full JSON body before matching', async () => {
  let releaseBody!: (payload: unknown) => void
  let matched = false
  const api = { path: '/api/v1/invoices', validate: (payload: unknown) => assert.deepEqual(payload, { items: [] }) }
  const matching = requiredBrowserResponse(response({ url: () => `${origin}${api.path}`, status: () => 200,
    json: () => new Promise(resolve => { releaseBody = resolve }) }), api, origin, true).then(value => { matched = value })
  await new Promise<void>(resolve => setImmediate(resolve))
  assert.equal(matched, false)
  releaseBody({ items: [] })
  await matching
  assert.equal(matched, true)
})
test('confirmed business-body cancellation never counts as a successful match', async () => {
  const api = { path: '/api/v1/invoices', validate: () => assert.fail('Canceled business body must not validate') }
  assert.equal(await requiredBrowserResponse(response({ url: () => `${origin}${api.path}`, status: () => 200,
    finished: async () => new Error('incomplete'), request: () => ({ method: () => 'GET', failure: () => ({ errorText: 'net::ERR_ABORTED' }) }) }), api, origin, true), false)
})
test('independent anonymous session GET waits for and validates complete JSON', async () => {
  let releaseBody!: (payload: unknown) => void
  let validated = false
  const validating = validateApiResponse(response({ json: () => new Promise(resolve => { releaseBody = resolve }) }),
    { ...session, validate: payload => { session.validate(payload); validated = true } })
  await new Promise<void>(resolve => setImmediate(resolve))
  assert.equal(validated, false)
  releaseBody({ error: { code: 'UNAUTHENTICATED' } })
  await validating
  assert.equal(validated, true)
})
test('independent anonymous session GET rejects malformed JSON', async () => {
  await assert.rejects(validateApiResponse(response({ json: async () => { throw new SyntaxError('invalid JSON') } }), session), /invalid JSON/)
})

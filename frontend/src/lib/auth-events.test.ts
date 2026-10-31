// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AUTH_EVENT_KEY, notifyAuthChange, subscribeAuthChanges } from './auth-events'
import { createApiClient } from './api'

afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })
describe('cross-tab authentication signals', () => {
  it('publishes only an event and timestamp and removes the storage marker', () => {
    const set = vi.spyOn(Storage.prototype, 'setItem')
    notifyAuthChange()
    expect(set).toHaveBeenCalledWith(AUTH_EVENT_KEY, expect.any(String))
    const event = JSON.parse(set.mock.calls.find(([key]) => key === AUTH_EVENT_KEY)![1])
    expect(Object.keys(event).sort()).toEqual(['event', 'timestamp'])
    expect(event.event).toBe('changed'); expect(typeof event.timestamp).toBe('number')
    expect(localStorage.getItem(AUTH_EVENT_KEY)).toBeNull()
  })
  it('reacts to valid remote changes but ignores removal, unrelated and malformed events', () => {
    const changed = vi.fn(), stop = subscribeAuthChanges(changed)
    for (const [key, newValue] of [[AUTH_EVENT_KEY, null], ['other', '{"event":"changed","timestamp":1}'], [AUTH_EVENT_KEY, '{'], [AUTH_EVENT_KEY, '{"event":"other","timestamp":1}']]) {
      window.dispatchEvent(new StorageEvent('storage', { key, newValue }))
    }
    expect(changed).not.toHaveBeenCalled()
    window.dispatchEvent(new StorageEvent('storage', { key: AUTH_EVENT_KEY, newValue: '{"event":"changed","timestamp":1}' }))
    expect(changed).toHaveBeenCalledTimes(1)
    stop()
    window.dispatchEvent(new StorageEvent('storage', { key: AUTH_EVENT_KEY, newValue: '{"event":"changed","timestamp":2}' }))
    expect(changed).toHaveBeenCalledTimes(1)
  })
  it('signals successful authority changes but never ordinary reads or rejected unlocks', async () => {
    const set = vi.spyOn(Storage.prototype, 'setItem')
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (_path, options) => new Response(JSON.stringify({ data: {} }), { status: new Headers(options?.headers).get('Reject-Test') ? 403 : 200 }))
    const client = createApiClient(fetcher)
    await client.request('/auth/session')
    await client.request('/dev-tools/status')
    await expect(client.request('/dev-tools/unlock', { method: 'POST', headers: { 'Reject-Test': 'yes' } })).rejects.toMatchObject({ status: 403 })
    expect(set).not.toHaveBeenCalled()
    for (const path of ['/auth/login', '/auth/logout', '/dev-tools/unlock', '/dev-tools/switch', '/dev-tools/end']) await client.request(path, { method: 'POST' })
    expect(set).toHaveBeenCalledTimes(5)
  })
})

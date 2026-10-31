// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../../lib'
import type { Actor, DevToolsStatus, SessionStatus } from '../../lib'
import { authNavigation, AUTH_EVENT_KEY } from '../../lib/auth-events'
import { DevToolsPage } from './DevToolsPage'
import { DevSessionBanner } from './DevSessionBanner'

const session = vi.hoisted(() => {
  const value: { status: SessionStatus; actor: Actor | null; devTools: DevToolsStatus | null; error: unknown; refresh: ReturnType<typeof vi.fn>; logout: ReturnType<typeof vi.fn> } = {
    status: 'authenticated', actor: null, devTools: null, error: null, refresh: vi.fn(), logout: vi.fn(),
  }
  return value
})
vi.mock('../../lib', async original => ({ ...await original<typeof import('../../lib')>(), useSession: () => session }))
const operator: Actor = { id: 'admin-1', name: 'Demo Operator', role: 'ADMIN', customer_id: null }
const target: Actor = { id: 'customer-user-1', name: 'Example Customer', role: 'CUSTOMER', customer_id: 'customer-1' }
function grant(actor = operator): Extract<DevToolsStatus, { unlocked: true }> {
  return { enabled: true, unlocked: true, dev_csrf_token: 'test-only-dev-csrf', expires_at: new Date(Date.now() + 60_000).toISOString(), operator: { id: operator.id, name: operator.name }, target: actor }
}
function page() { return render(<MemoryRouter initialEntries={['/dev']}><Routes><Route path="/dev" element={<DevToolsPage />} /><Route path="/sign-in" element={<h1>Administrator sign-in form</h1>} /></Routes></MemoryRouter>) }
function banner() { return render(<MemoryRouter><DevSessionBanner /></MemoryRouter>) }
beforeEach(() => {
  session.status = 'authenticated'; session.actor = operator; session.devTools = null; session.error = null
  session.refresh.mockReset().mockResolvedValue(undefined); session.logout.mockReset().mockResolvedValue(undefined)
  vi.spyOn(authNavigation, 'assign').mockImplementation(() => {})
  vi.spyOn(authNavigation, 'reload').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear() })
function unlockedRequests() {
  const status = grant(); session.devTools = status
  return vi.spyOn(apiClient, 'request').mockImplementation(async path => {
    if (path === '/dev-tools/status') return { data: status }
    if (path.startsWith('/dev-tools/accounts?')) return { items: [{ ...operator, email: 'operator@example.invalid' }, { ...target, email: 'customer@example.invalid' }], total: 2, page: 1, page_size: 25 }
    if (path === '/dev-tools/switch') return { data: { actor: target, csrf_token: 'new-normal-csrf', dev_tools: grant(target) } }
    throw new Error(`Unexpected test request ${path}`)
  })
}
describe('dedicated demo role testing', () => {
  it.each(['disabled', 'unavailable'])('handles %s tools without offering private access', async mode => {
    const request = vi.spyOn(apiClient, 'request')
    if (mode === 'disabled') request.mockResolvedValue({ data: { enabled: false, unlocked: false } })
    else request.mockRejectedValue(new ApiError(404, 'NOT_FOUND', 'Record not found.'))
    page()
    expect(await screen.findByRole('heading', { name: 'Role testing is unavailable' })).toBeVisible()
    expect(screen.queryByLabelText('Private developer password')).not.toBeInTheDocument()
    expect(request).toHaveBeenCalledTimes(1)
  })
  it('requires normal administrator sign-in before showing the separate developer password', async () => {
    session.status = 'anonymous'; session.actor = null
    vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { enabled: true, unlocked: false } })
    page()
    await screen.findByRole('heading', { name: 'Sign in as an administrator' })
    expect(screen.queryByLabelText('Private developer password')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Administrator sign-in' }))
    expect(screen.getByRole('heading', { name: 'Administrator sign-in form' })).toBeVisible()
  })
  it('keeps failed unlock explicit, clears the private password and never loads accounts', async () => {
    const request = vi.spyOn(apiClient, 'request').mockImplementation(async path => {
      if (path === '/dev-tools/status') return { data: { enabled: true, unlocked: false } }
      throw new ApiError(403, 'DEV_ACCESS_DENIED', 'Role testing could not be unlocked.')
    })
    page()
    await userEvent.type(await screen.findByLabelText('Private developer password'), 'test-only-private-password')
    await userEvent.click(screen.getByRole('button', { name: 'Unlock role testing' }))
    expect(await screen.findByText('Role testing could not be unlocked.')).toBeVisible()
    expect(screen.getByLabelText('Private developer password')).toHaveValue('')
    expect(request.mock.calls.some(([path]) => path.startsWith('/dev-tools/accounts'))).toBe(false)
  })
  it('uses returned active accounts and a separate developer CSRF header before full navigation', async () => {
    const request = unlockedRequests()
    page()
    await userEvent.click(await screen.findByRole('button', { name: 'Switch to Example Customer' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('customer permissions')
    await userEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    await waitFor(() => expect(authNavigation.assign).toHaveBeenCalledWith('/app'))
    expect(request).toHaveBeenCalledWith('/dev-tools/switch', { method: 'POST', json: { user_id: target.id }, headers: { 'X-Dev-CSRF-Token': 'test-only-dev-csrf' } })
    expect(localStorage.getItem(AUTH_EVENT_KEY)).toBeNull()
    expect(localStorage.length).toBe(0)
  })
  it('does not retry an uncertain switch or allow its confirmation to report success', async () => {
    const request = unlockedRequests(), original = request.getMockImplementation()!
    request.mockImplementation((path, options) => path === '/dev-tools/switch' ? Promise.reject(new ApiError(0, 'NETWORK_ERROR', 'Connection lost')) : original(path, options))
    page()
    await userEvent.click(await screen.findByRole('button', { name: 'Switch to Example Customer' }))
    await userEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    await screen.findByText('The request may have completed. Reload to verify your session before trying again.')
    await userEvent.click(screen.getByRole('button', { name: 'Switch account' }))
    expect(request.mock.calls.filter(([path]) => path === '/dev-tools/switch')).toHaveLength(1)
    expect(authNavigation.assign).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeVisible()
  })
  it('sends searched queries and aborts a stale account response on a newer search', async () => {
    const request = unlockedRequests(), original = request.getMockImplementation()!
    let staleSignal: AbortSignal | undefined
    request.mockImplementation((path, options) => {
      if (path.endsWith('q=first')) { staleSignal = options?.signal; return new Promise(() => {}) }
      return original(path, options)
    })
    page()
    await screen.findByText(target.name)
    await userEvent.type(screen.getByLabelText('Search accounts'), 'first')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(staleSignal).toBeDefined())
    await userEvent.clear(screen.getByLabelText('Search accounts'))
    await userEvent.type(screen.getByLabelText('Search accounts'), 'second')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    await waitFor(() => expect(request).toHaveBeenCalledWith('/dev-tools/accounts?page=1&page_size=25&q=second', expect.anything()))
    expect(staleSignal?.aborted).toBe(true)
  })
})
describe('persistent role-testing context', () => {
  it('keeps the operator, target and absolute expiry visible for a customer target', () => {
    session.actor = target; session.devTools = grant(target)
    banner()
    const context = screen.getByRole('complementary', { name: 'Role testing session' })
    expect(context).toHaveTextContent('Operator: Demo Operator')
    expect(context).toHaveTextContent('Current account: Example Customer (customer)')
    expect(context.querySelector('time')).toHaveAttribute('dateTime', session.devTools.expires_at)
  })
  it('fully navigates after returning a fresh original administrator session', async () => {
    session.actor = target; session.devTools = grant(target)
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { actor: operator, csrf_token: 'fresh-admin-csrf', dev_tools: { enabled: true, unlocked: false } } })
    banner()
    await userEvent.click(screen.getByRole('button', { name: 'End role testing' }))
    await waitFor(() => expect(authNavigation.assign).toHaveBeenCalledWith('/dev'))
    expect(request).toHaveBeenCalledWith('/dev-tools/end', { method: 'POST', headers: { 'X-Dev-CSRF-Token': 'test-only-dev-csrf' } })
  })
  it('invalidates and goes to sign-in for terminal expired/revoked/disabled end responses', async () => {
    session.actor = target; session.devTools = grant(target)
    const clear = vi.spyOn(apiClient, 'setCsrfToken')
    vi.spyOn(apiClient, 'request').mockRejectedValue(new ApiError(401, 'DEV_SESSION_EXPIRED', 'Role testing ended. Sign in again.'))
    banner()
    await userEvent.click(screen.getByRole('button', { name: 'End role testing' }))
    await waitFor(() => expect(authNavigation.assign).toHaveBeenCalledWith('/sign-in'))
    expect(clear).toHaveBeenCalledWith(null)
    expect(localStorage.length).toBe(0)
  })
  it('keeps context after a bad developer CSRF403 without retrying or navigating', async () => {
    session.actor = target; session.devTools = grant(target)
    const request = vi.spyOn(apiClient, 'request').mockRejectedValue(new ApiError(403, 'INVALID_DEV_CSRF', 'Refresh role testing and try again.'))
    banner()
    await userEvent.click(screen.getByRole('button', { name: 'End role testing' }))
    expect(await screen.findByText('Refresh role testing and try again.')).toBeVisible()
    expect(request).toHaveBeenCalledTimes(1)
    expect(authNavigation.assign).not.toHaveBeenCalled()
    expect(screen.getByRole('complementary', { name: 'Role testing session' })).toHaveTextContent(target.name)
  })
  it('clears the old CSRF state and reloads at absolute expiry without sending a mutation', async () => {
    vi.useFakeTimers()
    session.devTools = grant(); const clear = vi.spyOn(apiClient, 'setCsrfToken'), request = vi.spyOn(apiClient, 'request')
    banner()
    await act(async () => { vi.advanceTimersByTime(60_001) })
    expect(clear).toHaveBeenCalledWith(null)
    expect(authNavigation.reload).toHaveBeenCalledTimes(1)
    expect(request).not.toHaveBeenCalled()
  })
})

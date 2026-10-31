// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router'
import { apiClient, ApiError } from '../../lib'
import { AuthForm, passwordMeetsRequirements, StaffPage, workspaceDestination } from './index'

const session = vi.hoisted(() => ({ status: 'anonymous', refresh: vi.fn().mockResolvedValue(undefined) }))
vi.mock('../../lib', async importOriginal => ({ ...await importOriginal<typeof import('../../lib')>(), useSession: () => session }))
afterEach(() => { cleanup(); vi.restoreAllMocks() })
beforeEach(() => { session.status = 'anonymous'; session.refresh.mockClear() })
function page(mode: 'signin' | 'signup' | 'request' | 'reset', path = '/') {
  render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/app" element={<h1>Workspace</h1>} /><Route path="/form" element={<AuthForm mode={mode} />} /></Routes></MemoryRouter>)
}
async function credentials() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email address'), 'customer@example.com')
  await user.type(screen.getByLabelText('Password'), 'Abcdefgh!')
  return user
}

describe('identity forms', () => {
  it('preserves failed credentials and displays the useful API rejection', async () => {
    const request = vi.spyOn(apiClient, 'request').mockRejectedValue(new ApiError(401, 'INVALID_CREDENTIALS', 'Email or password is incorrect.'))
    page('signin', '/form')
    const user = await credentials()
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Email or password is incorrect.')).toBeTruthy()
    expect(screen.getByLabelText('Email address')).toHaveValue('customer@example.com')
    expect(screen.getByLabelText('Password')).toHaveValue('Abcdefgh!')
    expect(request).toHaveBeenCalledTimes(1)
    expect(session.refresh).not.toHaveBeenCalled()
  })

  it('refreshes the server session and enters the workspace after successful login', async () => {
    vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { actor: {}, csrf_token: 'test' } })
    page('signin', '/form')
    const user = await credentials()
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Workspace' })).toBeTruthy()
    expect(session.refresh).toHaveBeenCalledTimes(1)
  })

  it('blocks duplicate submission while a login request is pending', async () => {
    let finish!: (value: unknown) => void
    const request = vi.spyOn(apiClient, 'request').mockReturnValue(new Promise(resolve => { finish = resolve }))
    page('signin', '/form')
    const user = await credentials()
    await user.dblClick(screen.getByRole('button', { name: 'Sign in' }))
    expect(request).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
    await act(async () => finish({ data: {} }))
  })

  it('creates a customer account with compliant nine-character password and no role payload', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { id: 'customer' } })
    page('signup', '/form')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Your name'), 'Customer One')
    await credentials()
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Your customer account is ready. Sign in to continue.')).toBeTruthy()
    expect(request).toHaveBeenCalledWith('/auth/signup', { method: 'POST', json: { name: 'Customer One', email: 'customer@example.com', password: 'Abcdefgh!' } })
  })

  it('checks password requirements without introducing a digit requirement', () => {
    expect(passwordMeetsRequirements('Abcdefgh!')).toBe(true)
    for (const value of ['Abcdefg!', 'abcdefgh!', 'ABCDEFGH!', 'Abcdefghi', 'Abcdefgh ']) expect(passwordMeetsRequirements(value)).toBe(false)
  })

  it('shows the generic reset response without claiming email delivery', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { message: 'If this address is registered, a reset link will be sent.' } })
    page('request', '/form')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email address'), 'person@example.com')
    await user.click(screen.getByRole('button', { name: 'Request reset link' }))
    expect(await screen.findByText('If this address is registered, a reset link will be sent.')).toBeTruthy()
    expect(screen.getByText(/does not confirm delivery/)).toBeTruthy()
    expect(request).toHaveBeenCalledWith('/auth/password-reset/request', { method: 'POST', json: { email: 'person@example.com' } })
  })

  it('requires a complete reset link and does not send an empty token', () => {
    const request = vi.spyOn(apiClient, 'request')
    page('reset', '/form')
    expect(screen.getByRole('button', { name: 'Save new password' })).toBeDisabled()
    expect(screen.getByText('Reset link unavailable')).toBeTruthy()
    expect(request).not.toHaveBeenCalled()
  })

  it('rejects mismatched confirmation before sending the reset token', async () => {
    const request = vi.spyOn(apiClient, 'request')
    page('reset', '/form?token=test-reset-token')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('New password'), 'Abcdefgh!')
    await user.type(screen.getByLabelText('Confirm new password'), 'Different!')
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByText('The passwords do not match.')).toBeTruthy()
    expect(request).not.toHaveBeenCalled()
  })

  it('submits the reset token only to the API and clears password controls on success', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { password_reset: true } })
    page('reset', '/form?token=test-reset-token')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('New password'), 'Abcdefgh!')
    await user.type(screen.getByLabelText('Confirm new password'), 'Abcdefgh!')
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByText('Your password has been updated. Sign in with your new password.')).toBeTruthy()
    expect(screen.queryByDisplayValue('test-reset-token')).toBeNull()
    expect(screen.queryByLabelText('New password')).toBeNull()
    expect(request).toHaveBeenCalledWith('/auth/password-reset/confirm', { method: 'POST', json: { token: 'test-reset-token', new_password: 'Abcdefgh!' } })
  })

  it('creates staff through the backend and clears the temporary password', async () => {
    const request = vi.spyOn(apiClient, 'request').mockResolvedValue({ data: { id: 'staff', name: 'Staff One', role: 'STAFF', customer_id: null } })
    render(<MemoryRouter><StaffPage /></MemoryRouter>)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Staff name'), 'Staff One')
    await user.type(screen.getByLabelText('Staff email'), 'staff@example.com')
    await user.type(screen.getByLabelText('Temporary password'), 'Abcdefgh!')
    await user.click(screen.getByRole('button', { name: 'Create staff account' }))
    expect(await screen.findByText('Staff account created')).toBeTruthy()
    expect(screen.getByLabelText('Temporary password')).toHaveValue('')
    expect(request).toHaveBeenCalledWith('/staff', { method: 'POST', json: { name: 'Staff One', email: 'staff@example.com', temporary_password: 'Abcdefgh!' } })
  })
})

it('keeps post-login destinations within operational routes', () => {
  expect(workspaceDestination('/billing/invoices/example?from=home#payments')).toBe('/billing/invoices/example?from=home#payments')
  for (const value of ['//evil.example', '/\\evil.example', '/\n/evil.example', '/sign-in', '/app/../sign-in', '/%73ign-in', 'https://evil.example', null]) expect(workspaceDestination(value)).toBe('/app')
})

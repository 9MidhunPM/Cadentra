import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { FlaskConical, LockKeyhole, Search, ShieldCheck } from 'lucide-react'
import { apiClient, ApiError, getErrorMessage, isAbortError, useSession } from '../../lib'
import type { Actor, DevToolsStatus, ListResponse, ResourceResponse, SessionPayload } from '../../lib'
import { authNavigation } from '../../lib/auth-events'
import { validActor, validDevToolsStatus, validSessionPayload } from '../../lib/session-validation'
import { Button, ConfirmDialog, DataTable, ErrorPanel, FormField, LoadingSkeleton, PageHeader, StatusBadge } from '../../components/ui'
import { DevSessionBanner } from './DevSessionBanner'
import './dev-tools.css'

type Account = Actor & { email: string }
type StatusState = { loading: boolean; data: DevToolsStatus | null; unavailable: boolean; error: string | null }
export function DevToolsPage() {
  const session = useSession()
  const [status, setStatus] = useState<StatusState>({ loading: true, data: null, unavailable: false, error: null })
  const [revision, setRevision] = useState(0)
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [mutationError, setMutationError] = useState<string | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [accounts, setAccounts] = useState<{ loading: boolean; data: ListResponse<Account> | null; error: string | null }>({ loading: false, data: null, error: null })
  const mutation = useRef(false)
  useEffect(() => {
    const controller = new AbortController()
    setStatus({ loading: true, data: null, unavailable: false, error: null })
    apiClient.request<ResourceResponse<DevToolsStatus>>('/dev-tools/status', { signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return
      if (!validDevToolsStatus(result.data)) throw new ApiError(200, 'INVALID_RESPONSE', 'Role testing status could not be verified.')
      setStatus({ loading: false, data: result.data, unavailable: false, error: null })
    }).catch(caught => {
      if (controller.signal.aborted || isAbortError(caught)) return
      setStatus({ loading: false, data: null, unavailable: caught instanceof ApiError && caught.status === 404, error: caught instanceof ApiError && caught.status === 404 ? null : getErrorMessage(caught) })
    })
    return () => controller.abort()
  }, [revision, session.actor?.id])
  const grant = status.data?.unlocked ? status.data : null
  const available = !!grant && session.status === 'authenticated' && grant.target.id === session.actor?.id && Date.parse(grant.expires_at) > Date.now()
  useEffect(() => {
    if (!available) { setAccounts({ loading: false, data: null, error: null }); return }
    const controller = new AbortController()
    const params = new URLSearchParams({ page: String(page), page_size: '25', q: query })
    setAccounts({ loading: true, data: null, error: null })
    apiClient.request<ListResponse<Account>>(`/dev-tools/accounts?${params}`, { signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return
      if (!result.items.every(account => validActor(account) && typeof account.email === 'string')) throw new ApiError(200, 'INVALID_RESPONSE', 'The account list could not be verified.')
      setAccounts({ loading: false, data: result, error: null })
    }).catch(caught => { if (!controller.signal.aborted && !isAbortError(caught)) setAccounts({ loading: false, data: null, error: getErrorMessage(caught) }) })
    return () => controller.abort()
  }, [available, page, query, revision])
  async function unlock(event: FormEvent) {
    event.preventDefault()
    if (mutation.current || session.actor?.role !== 'ADMIN' || !password || uncertain) return
    mutation.current = true; setPending(true); setMutationError(null)
    try {
      const result = await apiClient.request<ResourceResponse<DevToolsStatus>>('/dev-tools/unlock', { method: 'POST', json: { password } })
      if (!validDevToolsStatus(result.data) || !result.data.unlocked || result.data.operator.id !== session.actor.id || result.data.target.id !== session.actor.id) throw new ApiError(200, 'INVALID_RESPONSE', 'Reload to verify role testing before continuing.')
      setStatus({ loading: false, data: result.data, unavailable: false, error: null })
      await session.refresh()
    } catch (caught) { failedMutation(caught) }
    finally { setPassword(''); mutation.current = false; setPending(false) }
  }
  function failedMutation(caught: unknown) {
    const unknown = !(caught instanceof ApiError && caught.status >= 400 && caught.status < 500 && caught.status !== 408 && caught.code !== 'INVALID_RESPONSE')
    setUncertain(unknown)
    setMutationError(unknown ? 'The request may have completed. Reload to verify your session before trying again.' : getErrorMessage(caught))
  }
  async function switchAccount(account: Account) {
    if (!grant || !available || mutation.current || uncertain) throw new ApiError(409, 'SESSION_RECHECK_REQUIRED', 'Reload to verify your current session before switching accounts.')
    mutation.current = true; setPending(true); setMutationError(null)
    try {
      const result = await apiClient.request<ResourceResponse<SessionPayload>>('/dev-tools/switch', { method: 'POST', json: { user_id: account.id }, headers: { 'X-Dev-CSRF-Token': grant.dev_csrf_token } })
      if (!validSessionPayload(result.data) || result.data.actor.id !== account.id || !result.data.dev_tools?.unlocked || result.data.dev_tools.operator.id !== grant.operator.id) throw new ApiError(200, 'INVALID_RESPONSE', 'Reload to verify the active account before continuing.')
      apiClient.setCsrfToken(result.data.csrf_token)
      authNavigation.assign('/app')
    } catch (caught) { failedMutation(caught); throw caught }
    finally { mutation.current = false; setPending(false) }
  }
  return <div className="dev-tools-page">
    <header className="dev-tools-topbar"><Link to="/" className="dev-tools-brand">Cadentra<span>.</span></Link><Link to="/app">Open workspace</Link></header>
    <DevSessionBanner />
    <main className="dev-tools-main">
      <PageHeader eyebrow="DEMO INSTANCE" title="Role testing" description="See the workspace through an existing account’s permissions." />
      <section className="dev-tools-intro"><span className="dev-tools-symbol"><FlaskConical size={26} aria-hidden="true" /></span><div><h2>A deliberate change of perspective.</h2><p>Choose a saved account to test its actual staff or customer experience. Permissions, saved changes and email rules still apply.</p></div></section>
      {mutationError ? <ErrorPanel title={uncertain ? 'Verify your session' : 'Role testing request failed'} message={mutationError} /> : null}
      {uncertain ? <Button variant="secondary" onClick={() => authNavigation.assign('/dev')}>Reload session</Button> : null}
      {status.loading || session.status === 'loading' ? <LoadingSkeleton label="Checking role testing access" />
        : status.unavailable || status.data?.enabled === false ? <section className="dev-tools-card"><LockKeyhole size={24} aria-hidden="true" /><h2>Role testing is unavailable</h2><p>This optional tool is disabled on this instance. Use the normal sign-in and workspace.</p><Link to="/app">Return to the workspace</Link></section>
        : status.error ? <ErrorPanel title="Role testing could not load" message={status.error} onRetry={() => setRevision(value => value + 1)} />
        : session.status === 'error' ? <ErrorPanel title="Your session could not load" message={getErrorMessage(session.error)} onRetry={() => void session.refresh()} />
        : session.status === 'anonymous' ? <section className="dev-tools-card"><ShieldCheck size={24} aria-hidden="true" /><span className="dev-tools-step">STEP 1 OF 2</span><h2>Sign in as an administrator</h2><p>Use your normal administrator account first. The private role-testing password is a separate step.</p><Link className="ui-button ui-button--primary" to="/sign-in" state={{ from: '/dev' }}>Administrator sign-in</Link></section>
        : !grant ? <section className="dev-tools-card"><LockKeyhole size={24} aria-hidden="true" /><span className="dev-tools-step">STEP 2 OF 2</span><h2>Unlock role testing</h2>{session.actor?.role === 'ADMIN' ? <><p>Signed in as <strong>{session.actor.name}</strong>. Enter the private developer password to continue.</p><form onSubmit={event => void unlock(event)} className="dev-tools-unlock"><FormField id="dev-password" label="Private developer password" hint="Use the private password for this demo instance, not your administrator sign-in password."><input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="off" required maxLength={1024} disabled={pending || uncertain} /></FormField><Button type="submit" pending={pending} disabled={uncertain}>Unlock role testing</Button></form></> : <><p>This requires a normal administrator session. End your current sign-in, then return here with an administrator account.</p><Button variant="secondary" pending={pending} onClick={() => { if (mutation.current) return; mutation.current = true; setPending(true); void session.logout().then(() => authNavigation.assign('/dev')).catch(caught => setMutationError(getErrorMessage(caught))).finally(() => { mutation.current = false; setPending(false) }) }}>Sign out to change administrator</Button></>}</section>
        : !available ? <ErrorPanel title="Role testing needs a fresh session" message="The grant expired or the current account changed. Reload before continuing." onRetry={() => authNavigation.assign('/dev')} />
        : <section className="dev-tools-accounts"><div className="dev-tools-account-heading"><div><h2>Choose an account</h2><p>Only active accounts are returned by the server.</p></div><span className="dev-tools-readonly">Account selection · real permissions</span></div><form className="dev-tools-search" onSubmit={event => { event.preventDefault(); setQuery(search.trim()); setPage(1); setRevision(value => value + 1) }}><FormField id="dev-account-search" label="Search accounts"><input type="search" value={search} onChange={event => setSearch(event.target.value)} maxLength={200} placeholder="Name or email" disabled={pending || uncertain} /></FormField><Button variant="secondary" type="submit" disabled={pending || uncertain}><Search size={16} aria-hidden="true" />Search</Button></form>
          {accounts.loading ? <LoadingSkeleton label="Loading active accounts" /> : accounts.error ? <ErrorPanel title="Accounts unavailable" message={accounts.error} onRetry={() => setRevision(value => value + 1)} /> : accounts.data ? <DataTable caption="Active accounts" rows={accounts.data.items} getRowKey={account => account.id} page={accounts.data.page} pageSize={accounts.data.page_size} total={accounts.data.total} onPageChange={next => { if (!pending && !uncertain) setPage(next) }} emptyTitle="No active accounts match your search" columns={[
            { key: 'account', header: 'Account', render: account => <span className="dev-tools-account-name"><strong>{account.name}</strong><small>{account.email}</small></span> },
            { key: 'role', header: 'Access', render: account => <StatusBadge status={account.role} /> },
            { key: 'action', header: 'Use account', render: account => account.id === session.actor?.id ? <span className="dev-tools-current">Current account</span> : <ConfirmDialog title={`Switch to ${account.name}?`} description={`You will use this account’s ${account.role.toLowerCase()} permissions. Actions in the workspace affect saved records.`} confirmLabel="Switch account" trigger={<Button variant="secondary" disabled={pending || uncertain} aria-label={`Switch to ${account.name}`}>Use account</Button>} onConfirm={() => switchAccount(account)} /> },
          ]} /> : null}
        </section>}
    </main><footer className="dev-tools-footer">Cadentra · Explicit demo role testing</footer>
  </div>
}

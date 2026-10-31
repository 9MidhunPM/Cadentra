import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { FlaskConical } from 'lucide-react'
import { apiClient, ApiError, getErrorMessage, useSession } from '../../lib'
import type { ResourceResponse, SessionPayload } from '../../lib'
import { authNavigation, notifyAuthChange } from '../../lib/auth-events'
import { validSessionPayload } from '../../lib/session-validation'
import { Button } from '../../components/ui'
import './dev-tools.css'

export function DevSessionBanner() {
  const { devTools } = useSession()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lock = useRef(false)
  const uncertain = useRef(false)
  useEffect(() => {
    if (!devTools?.unlocked) return
    const remaining = Date.parse(devTools.expires_at) - Date.now()
    // A fresh document rechecks server authority and clears retained actor state.
    const timer = window.setTimeout(() => { apiClient.setCsrfToken(null); authNavigation.reload() }, Math.max(0, Math.min(remaining, 2_147_483_647)))
    return () => window.clearTimeout(timer)
  }, [devTools])
  if (!devTools?.unlocked) return null
  const expired = Date.parse(devTools.expires_at) <= Date.now()
  async function end() {
    if (!devTools?.unlocked || lock.current || expired || uncertain.current) return
    lock.current = true; setPending(true); setError(null)
    try {
      const result = await apiClient.request<ResourceResponse<SessionPayload>>('/dev-tools/end', { method: 'POST', headers: { 'X-Dev-CSRF-Token': devTools.dev_csrf_token } })
      if (!validSessionPayload(result.data) || result.data.actor.id !== devTools.operator.id || result.data.actor.role !== 'ADMIN' || result.data.dev_tools?.unlocked !== false) {
        throw new ApiError(200, 'INVALID_RESPONSE', 'Reload to verify which account is active before continuing.')
      }
      apiClient.setCsrfToken(result.data.csrf_token)
      authNavigation.assign('/dev')
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) { apiClient.setCsrfToken(null); notifyAuthChange(); authNavigation.assign('/sign-in'); return }
      uncertain.current = !(caught instanceof ApiError && caught.status >= 400 && caught.status < 500 && caught.status !== 408 && caught.code !== 'INVALID_RESPONSE')
      setError(uncertain.current ? 'The session may have changed. Reload to verify your account before trying again.' : getErrorMessage(caught))
    } finally { lock.current = false; setPending(false) }
  }
  return <aside className="dev-session-banner" aria-label="Role testing session">
    <div className="dev-session-context"><FlaskConical size={20} aria-hidden="true" /><div><strong>Role testing is active</strong><p>Operator: {devTools.operator.name} <span aria-hidden="true">→</span> Current account: {devTools.target.name} ({devTools.target.role.toLowerCase()})</p><p>Ends <time dateTime={devTools.expires_at} title={devTools.expires_at}>{new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'long' }).format(new Date(devTools.expires_at))}</time>. Actions affect saved records.</p></div></div>
    <div className="dev-session-actions"><Link to="/dev">Choose account</Link><Button variant="secondary" pending={pending} disabled={expired || uncertain.current} onClick={() => void end()}>End role testing</Button></div>
    {error ? <div className="dev-session-error" role="alert"><span>{error}</span><Button variant="secondary" onClick={() => authNavigation.assign('/dev')}>Reload session</Button></div> : null}
  </aside>
}

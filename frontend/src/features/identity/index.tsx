import { useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams, type RouteObject } from 'react-router'
import { ArrowRight, Layers3, LockKeyhole, ShieldCheck } from 'lucide-react'
import { Button, ErrorPanel, FormField, PageHeader } from '../../components/ui'
import { apiClient, ApiError, getErrorMessage, useSession } from '../../lib'
import type { Actor, ResourceResponse, SessionPayload } from '../../lib'
import './identity.css'


export function workspaceDestination(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || [...value].some(character => character === '\\' || character.charCodeAt(0) <= 32)) return '/app'
  try {
    const url = new URL(value, window.location.origin)
    if (url.origin !== window.location.origin || !/^\/(?:app|overview|cycleguard|customers|catalog|subscriptions|billing|portal|settings)(?:\/|$)/.test(url.pathname)) return '/app'
    return `${url.pathname}${url.search}${url.hash}`
  } catch { return '/app' }
}

type Mode = 'signin' | 'signup' | 'request' | 'reset'
const passwordHint = 'At least nine characters, with uppercase, lowercase and a special character.'
const copy: Record<Mode, { title: string; description: string; submit: string }> = {
  signin: { title: 'Welcome back.', description: 'Your subscriptions, customers and every cycle in one place.', submit: 'Sign in' },
  signup: { title: 'Make yourself at home.', description: 'Create a customer account to manage your Brightloop services.', submit: 'Create account' },
  request: { title: 'Find your way back.', description: 'Enter your registered email to request a password reset link.', submit: 'Request reset link' },
  reset: { title: 'A fresh start.', description: 'Choose a new password for your Cadentra account.', submit: 'Save new password' },
}

export function passwordMeetsRequirements(value: string) {
  return [...value].length >= 9 && /\p{Lu}/u.test(value) && /\p{Ll}/u.test(value) && /[^\p{L}\p{N}\s]/u.test(value)
}

function fieldError(error: unknown, name: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined
  const value = error.fields[name] ?? error.fields[`body.${name}`]
  return typeof value === 'string' ? value : undefined
}

function AuthLayout({ children }: { children: ReactNode }) {
  return <main className="identity-experience">
    <section className="identity-story" aria-label="About Cadentra">
      <Link to="/" className="identity-brand"><Layers3 size={27} aria-hidden="true" />Cadentra<span>.</span></Link>
      <div><span className="identity-overline">BRIGHTLOOP SOFTWARE</span><h2>Every subscription.<br />Every cycle.<br /><span>Accounted for.</span></h2><p>A clear view of your services, invoices and the details that keep everything moving.</p></div>
      <div className="identity-story-footer"><ShieldCheck size={20} aria-hidden="true" /><span>Your workspace. Your account.</span></div>
    </section>
    <section className="identity-card">{children}</section>
  </main>
}

export function AuthForm({ mode }: { mode: Mode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const destination = workspaceDestination(location.state?.from)
  const [params, setParams] = useSearchParams()
  const { status, refresh } = useSession()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const submitting = useRef(false)
  const token = params.get('token') || ''
  const needsPassword = mode !== 'request'
  const newPassword = mode === 'signup' || mode === 'reset'
  const invalidToken = mode === 'reset' && (!token || token.length > 256)
  if (mode === 'signin' && status === 'authenticated') return <Navigate to={destination} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current || invalidToken) return
    setError(null)
    if (newPassword && !passwordMeetsRequirements(password)) {
      setError(new ApiError(422, 'INVALID_PASSWORD', passwordHint, { password: passwordHint }))
      return
    }
    if (mode === 'reset' && password !== confirmation) {
      setError(new ApiError(422, 'PASSWORD_MISMATCH', 'The passwords do not match.', { confirmation: 'Enter the same password in both fields.' }))
      return
    }
    submitting.current = true
    setPending(true)
    try {
      if (mode === 'signin') {
        await apiClient.request<ResourceResponse<SessionPayload>>('/auth/login', { method: 'POST', json: { email, password } })
        setPassword('')
        await refresh()
        navigate(destination, { replace: true })
      } else if (mode === 'signup') {
        await apiClient.request<ResourceResponse<Actor>>('/auth/signup', { method: 'POST', json: { name, email, password } })
        setPassword('')
        setSuccess('Your customer account is ready. Sign in to continue.')
      } else if (mode === 'request') {
        const result = await apiClient.request<ResourceResponse<{ message: string }>>('/auth/password-reset/request', { method: 'POST', json: { email } })
        setSuccess(result.data.message)
      } else {
        await apiClient.request('/auth/password-reset/confirm', { method: 'POST', json: { token, new_password: password } })
        setPassword('')
        setConfirmation('')
        setSuccess('Your password has been updated. Sign in with your new password.')
        setParams(current => { const next = new URLSearchParams(current); next.delete('token'); return next }, { replace: true })
        await refresh()
      }
    } catch (caught) { setError(caught) }
    finally { submitting.current = false; setPending(false) }
  }

  return <AuthLayout>
    <div className="identity-card-heading"><span className="identity-lock"><LockKeyhole size={22} aria-hidden="true" /></span><p className="identity-overline">YOUR CADENTRA ACCOUNT</p><h1>{copy[mode].title}</h1><p className="ui-muted">{copy[mode].description}</p></div>
    {success ? <div className="identity-result" role="status"><ShieldCheck aria-hidden="true" /><h2>{mode === 'request' ? 'Check your inbox' : 'You’re all set'}</h2><p>{success}</p>{mode === 'request' && <p className="ui-muted">A requested link may take a little time. Check your spam folder too. This message does not confirm delivery.</p>}<Link to="/sign-in" className="identity-text-link">Back to sign in <ArrowRight size={16} aria-hidden="true" /></Link>{mode === 'request' && <Button variant="secondary" onClick={() => setSuccess(null)}>Request another link</Button>}</div> : <form className="identity-form" onSubmit={event => void submit(event)}>
      {invalidToken && <ErrorPanel title="Reset link unavailable" message="Open the complete link from your reset email, or request a new link." />}
      {error != null && <ErrorPanel title="We couldn’t complete that request" message={getErrorMessage(error)} />}
      {mode === 'signup' && <FormField id="identity-name" label="Your name" error={fieldError(error, 'name')}><input name="name" autoComplete="name" value={name} onChange={event => setName(event.target.value)} required maxLength={200} disabled={pending} /></FormField>}
      {mode !== 'reset' && <FormField id="identity-email" label="Email address" error={fieldError(error, 'email')}><input name="email" type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} required maxLength={320} disabled={pending} /></FormField>}
      {needsPassword && <FormField id="identity-password" label={mode === 'reset' ? 'New password' : 'Password'} hint={newPassword ? passwordHint : undefined} error={fieldError(error, 'password') ?? fieldError(error, 'new_password')}><input name="password" type="password" autoComplete={newPassword ? 'new-password' : 'current-password'} value={password} onChange={event => setPassword(event.target.value)} required minLength={newPassword ? 9 : 1} maxLength={1024} disabled={pending || invalidToken} /></FormField>}
      {mode === 'reset' && <FormField id="identity-confirmation" label="Confirm new password" error={fieldError(error, 'confirmation')}><input name="confirmation" type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} required maxLength={1024} disabled={pending || invalidToken} /></FormField>}
      <Button type="submit" pending={pending} disabled={invalidToken}>{copy[mode].submit}<ArrowRight size={17} aria-hidden="true" /></Button>
    </form>}
    <div className="identity-footer-links">{mode === 'signin' ? <><Link to="/sign-up">Create a customer account</Link><Link to="/forgot-password">Forgot password?</Link></> : <Link to="/sign-in">Already have an account? Sign in</Link>}{mode === 'reset' && <Link to="/forgot-password">Request a new reset link</Link>}</div>
  </AuthLayout>
}

export function StaffPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [created, setCreated] = useState<Actor | null>(null)
  const submitting = useRef(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current) return
    setError(null)
    setCreated(null)
    if (!passwordMeetsRequirements(password)) { setError(new ApiError(422, 'INVALID_PASSWORD', passwordHint, { temporary_password: passwordHint })); return }
    submitting.current = true
    setPending(true)
    try {
      const result = await apiClient.request<ResourceResponse<Actor>>('/staff', { method: 'POST', json: { name, email, temporary_password: password } })
      setCreated(result.data)
      setPassword('')
      setName('')
      setEmail('')
    } catch (caught) { setError(caught) }
    finally { submitting.current = false; setPending(false) }
  }
  return <><PageHeader eyebrow="ACCESS MANAGEMENT" title="Staff settings" description="Give your team access to subscription operations. Only administrators can create staff accounts." /><section className="identity-staff-panel"><div><h2>Add a staff member</h2><p className="ui-muted">Share the temporary password securely with the account holder. Passwords are not emailed by this form.</p></div>{created && <div className="identity-result" role="status"><h3>Staff account created</h3><p>{created.name} can now sign in with the email address you provided.</p></div>}{error != null && <ErrorPanel message={getErrorMessage(error)} />}<form className="identity-form" onSubmit={event => void submit(event)}><FormField id="staff-name" label="Staff name" error={fieldError(error, 'name')}><input value={name} onChange={event => setName(event.target.value)} autoComplete="name" required maxLength={200} disabled={pending} /></FormField><FormField id="staff-email" label="Staff email" error={fieldError(error, 'email')}><input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="off" required maxLength={320} disabled={pending} /></FormField><FormField id="staff-password" label="Temporary password" hint={passwordHint} error={fieldError(error, 'temporary_password') ?? fieldError(error, 'password')}><input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" required minLength={9} maxLength={1024} disabled={pending} /></FormField><div><Button type="submit" pending={pending}>Create staff account</Button></div></form></section></>
}

export function getRoutes(): RouteObject[] {
  return [
    { path: '/sign-in', element: <AuthForm key="signin" mode="signin" /> },
    { path: '/sign-up', element: <AuthForm key="signup" mode="signup" /> },
    { path: '/forgot-password', element: <AuthForm key="request" mode="request" /> },
    { path: '/reset-password', element: <AuthForm key="reset" mode="reset" /> },
  ]
}
export function getStaffRoutes(): RouteObject[] {
  return [{ path: '/settings/staff', element: <StaffPage /> }]
}

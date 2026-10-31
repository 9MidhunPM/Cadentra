import { Link, Navigate, Outlet, useLocation } from 'react-router'
import { useSession, getErrorMessage } from '../lib'
import type { Role } from '../lib'

export function RoleGuard({ roles }: { roles: readonly Role[] }) {
  const { status, actor, error, refresh } = useSession()
  const location = useLocation()
  if (status === 'loading') return <div className="standalone-page" role="status"><div className="loading-line" /><p>Restoring your session…</p></div>
  if (status === 'error') return <div className="standalone-page"><span className="connection-symbol" aria-hidden="true">!</span><h1>We couldn’t connect</h1><p role="alert">{getErrorMessage(error)}</p><button className="primary-button" onClick={() => void refresh()}>Try again</button></div>
  if (status === 'anonymous') return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  if (!actor || !roles.includes(actor.role)) return <div className="standalone-page"><h1>Access restricted</h1><p>Your account does not have access to this workspace.</p><Link to="/app">Return to your workspace</Link></div>
  return <Outlet />
}

export function Landing() {
  const { actor } = useSession()
  return <Navigate to={actor?.role === 'CUSTOMER' ? '/portal/subscriptions' : '/overview'} replace />
}

import type { RouteObject } from 'react-router'
import { Link } from 'react-router'
import { FeaturePlaceholder } from '../../app/FeaturePlaceholder'

// Bootstrap placeholders; identity feature ownership transfers to Midhun P M.
export function getRoutes(): RouteObject[] {
  return [
    { path: '/sign-in', element: <div className="identity-page"><Link className="identity-wordmark" to="/">Cadentra.</Link><FeaturePlaceholder title="Sign in" description="Access your Brightloop workspace." /><div className="identity-links"><Link to="/sign-up">Create a customer account</Link><Link to="/forgot-password">Forgot password?</Link></div></div> },
    { path: '/sign-up', element: <FeaturePlaceholder title="Create an account" description="Your Brightloop customer account." /> },
    { path: '/forgot-password', element: <FeaturePlaceholder title="Reset your password" description="Recover access to your account." /> },
    { path: '/reset-password', element: <FeaturePlaceholder title="Choose a new password" description="Restore access securely." /> },
  ]
}

export function getStaffRoutes(): RouteObject[] {
  return [{ path: '/settings/staff', element: <FeaturePlaceholder title="Staff settings" description="Manage access to your Brightloop workspace." /> }]
}

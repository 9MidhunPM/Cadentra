import { createBrowserRouter, Outlet } from 'react-router'
import { AppShell } from './AppShell'
import { Landing, RoleGuard } from './RoleGuard'
import { NotFound } from './FeaturePlaceholder'
import { getRoutes as identityRoutes, getStaffRoutes } from '../features/identity'
import { getRoutes as catalogRoutes } from '../features/catalog'
import { getRoutes as subscriptionRoutes } from '../features/subscriptions'
import { getRoutes as billingRoutes } from '../features/billing'
import { getRoutes as reportingRoutes } from '../features/reporting'
import { getRoutes as portalRoutes } from '../features/portal'
import { PageNavigation } from './PageNavigation'
import { RouteErrorBoundary } from './RouteErrorBoundary'

export function createAppRouter() {
  return createBrowserRouter([{
    element: <><PageNavigation /><Outlet /></>,
    errorElement: <RouteErrorBoundary />,
    children: [
    ...identityRoutes(),
    { element: <RoleGuard roles={['ADMIN', 'STAFF', 'CUSTOMER']} />, children: [{ path: '/', element: <Landing /> }] },
    { element: <RoleGuard roles={['ADMIN', 'STAFF']} />, children: [{ element: <AppShell />, children: [...catalogRoutes(), ...subscriptionRoutes(), ...billingRoutes(), ...reportingRoutes()] }] },
    { element: <RoleGuard roles={['ADMIN']} />, children: [{ element: <AppShell />, children: getStaffRoutes() }] },
    { element: <RoleGuard roles={['CUSTOMER']} />, children: [{ element: <AppShell />, children: portalRoutes() }] },
    { path: '*', element: <NotFound /> },
    ],
  }])
}

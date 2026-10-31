import type { RouteObject } from 'react-router'
import { OverviewPage } from './OverviewPage'
import { CycleGuardPage } from './CycleGuardPage'

export function getRoutes(): RouteObject[] {
  return [{ path: '/overview', element: <OverviewPage /> }, { path: '/cycleguard', element: <CycleGuardPage /> }]
}

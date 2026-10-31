import type { RouteObject } from 'react-router'
import { OverviewPage } from './OverviewPage'

export function getRoutes(): RouteObject[] {
  return [{ path: '/overview', element: <OverviewPage /> }]
}

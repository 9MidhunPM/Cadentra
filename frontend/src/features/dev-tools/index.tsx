import type { RouteObject } from 'react-router'
import { DevToolsPage } from './DevToolsPage'
export function getRoutes(): RouteObject[] { return [{ path: '/dev', element: <DevToolsPage /> }] }

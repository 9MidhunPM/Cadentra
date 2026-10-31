import { createBrowserRouter, Outlet, type RouteObject } from 'react-router'
import { Landing, RoleGuard } from './RoleGuard'
import { NotFound } from './FeaturePlaceholder'
import { PageNavigation } from './PageNavigation'
import { RouteErrorBoundary } from './RouteErrorBoundary'

type Feature = { getRoutes: () => RouteObject[] }
function feature(path: string, load: () => Promise<Feature>): RouteObject {
  return { path, lazy: async () => {
    const route = (await load()).getRoutes().find(item => item.path === path)
    if (!route?.element) throw new Error('Page unavailable')
    return { Component: () => <>{route.element}</> }
  } }
}
const catalog = () => import('../features/catalog')
const subscriptions = () => import('../features/subscriptions')
const billing = () => import('../features/billing')
const reporting = () => import('../features/reporting')
const portal = () => import('../features/portal')
const identity = () => import('../features/identity')
const devTools = () => import('../features/dev-tools')
const shell = async () => ({ Component: (await import('./AppShell')).AppShell })

export function createAppRouter() {
  return createBrowserRouter([{
    element: <><PageNavigation /><Outlet /></>,
    HydrateFallback: () => <main className="standalone-page" role="status"><p>Opening Cadentra…</p></main>,
    errorElement: <RouteErrorBoundary />,
    children: [
      { path: '/', lazy: async () => ({ Component: (await import('../features/home')).default }) },
      feature('/dev', devTools),
      ...['/sign-in', '/sign-up', '/forgot-password', '/reset-password'].map(path => feature(path, identity)),
      { element: <RoleGuard roles={['ADMIN', 'STAFF', 'CUSTOMER']} />, children: [{ path: '/app', element: <Landing /> }] },
      { element: <RoleGuard roles={['ADMIN', 'STAFF']} />, children: [{ lazy: shell, children: [
        ...['/customers', '/catalog/products', '/catalog/plans'].map(path => feature(path, catalog)),
        ...['/subscriptions', '/subscriptions/new', '/subscriptions/templates', '/subscriptions/templates/new', '/subscriptions/templates/:id/edit', '/subscriptions/:id'].map(path => feature(path, subscriptions)),
        ...['/billing/invoices', '/billing/invoices/:id', '/billing/taxes', '/billing/discounts'].map(path => feature(path, billing)),
        ...['/overview', '/cycleguard'].map(path => feature(path, reporting)),
      ] }] },
      { element: <RoleGuard roles={['ADMIN']} />, children: [{ lazy: shell, children: [feature('/settings/staff', async () => ({ getRoutes: (await identity()).getStaffRoutes }))] }] },
      { element: <RoleGuard roles={['CUSTOMER']} />, children: [{ lazy: shell, children: ['/portal/subscriptions', '/portal/subscriptions/:id', '/portal/invoices', '/portal/invoices/:id', '/portal/account'].map(path => feature(path, portal)) }] },
      { path: '*', element: <NotFound /> },
    ],
  }])
}

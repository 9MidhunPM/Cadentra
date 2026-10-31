import type { RouteObject } from 'react-router'
import { FeaturePlaceholder } from '../../app/FeaturePlaceholder'

export function getRoutes(): RouteObject[] {
  return [
    { path: '/portal/subscriptions', element: <FeaturePlaceholder title="My subscriptions" description="Your services, dates and subscription details." /> },
    { path: '/portal/subscriptions/:id', element: <FeaturePlaceholder title="My subscription" description="Your service dates and available actions." /> },
    { path: '/portal/invoices', element: <FeaturePlaceholder title="My invoices" description="Your invoices, recorded payments and balances." /> },
    { path: '/portal/invoices/:id', element: <FeaturePlaceholder title="My invoice" description="Your invoice and payment history." /> },
    { path: '/portal/account', element: <FeaturePlaceholder title="Account" description="Your Brightloop customer profile." /> },
  ]
}

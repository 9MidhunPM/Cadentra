import type { RouteObject } from 'react-router'
import { FeaturePlaceholder } from '../../app/FeaturePlaceholder'

// Bootstrap placeholders; catalog feature ownership transfers to Midhun P M.
export function getRoutes(): RouteObject[] {
  return [
    { path: '/customers', element: <FeaturePlaceholder title="Customers" description="The people and businesses behind every subscription." /> },
    { path: '/catalog/products', element: <FeaturePlaceholder title="Products" description="Your products, variants and recurring charges." /> },
    { path: '/catalog/plans', element: <FeaturePlaceholder title="Plans" description="Billing schedules and policies, in one place." /> },
  ]
}

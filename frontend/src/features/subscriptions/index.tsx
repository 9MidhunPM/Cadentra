import type { RouteObject } from 'react-router'
import { FeaturePlaceholder } from '../../app/FeaturePlaceholder'

// Bootstrap placeholders; subscription feature ownership transfers to Thanushree Suresh.
export function getRoutes(): RouteObject[] {
  return [
    { path: '/subscriptions', element: <FeaturePlaceholder title="Subscriptions" description="Follow every subscription from quotation to closure." /> },
    { path: '/subscriptions/templates', element: <FeaturePlaceholder title="Quotation templates" description="Consistent offers for your recurring business." /> },
    { path: '/subscriptions/:id', element: <FeaturePlaceholder title="Subscription details" description="Service dates, agreed charges and lifecycle actions." /> },
  ]
}

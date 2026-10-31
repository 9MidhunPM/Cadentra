import type { RouteObject } from 'react-router'
import { FeaturePlaceholder } from '../../app/FeaturePlaceholder'

// Bootstrap placeholders; billing feature ownership transfers to Noel Biju.
export function getRoutes(): RouteObject[] {
  return [
    { path: '/billing/invoices', element: <FeaturePlaceholder title="Invoices" description="Every billing period, invoice and payment accounted for." /> },
    { path: '/billing/invoices/:id', element: <FeaturePlaceholder title="Invoice details" description="Stored charges, taxes, payments and balance." /> },
    { path: '/billing/taxes', element: <FeaturePlaceholder title="Tax rules" description="Tax configuration for your recurring charges." /> },
    { path: '/billing/discounts', element: <FeaturePlaceholder title="Discounts" description="Clear rules for eligible recurring discounts." /> },
  ]
}

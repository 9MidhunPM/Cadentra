import type { RouteObject } from 'react-router';
import { InvoiceDetail, InvoiceList } from './invoices';
import { RulePage } from './rules';
import './billing.css';

export function getRoutes(): RouteObject[] {
  return [
    { path: '/billing/invoices', element: <InvoiceList /> },
    { path: '/billing/invoices/:id', element: <InvoiceDetail /> },
    { path: '/billing/taxes', element: <RulePage key="tax" kind="tax" /> },
    { path: '/billing/discounts', element: <RulePage key="discount" kind="discount" /> },
  ];
}

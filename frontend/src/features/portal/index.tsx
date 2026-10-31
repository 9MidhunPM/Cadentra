import type { RouteObject } from "react-router";
import {
  AccountPage,
  InvoiceDetailPage,
  InvoiceListPage,
  SubscriptionDetailPage,
  SubscriptionListPage,
} from "./PortalPages";

export function getRoutes(): RouteObject[] {
  return [
    { path: "/portal/subscriptions", element: <SubscriptionListPage /> },
    { path: "/portal/subscriptions/:id", element: <SubscriptionDetailPage /> },
    { path: "/portal/invoices", element: <InvoiceListPage /> },
    { path: "/portal/invoices/:id", element: <InvoiceDetailPage /> },
    { path: "/portal/account", element: <AccountPage /> },
  ];
}

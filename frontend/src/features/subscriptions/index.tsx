import type { RouteObject } from 'react-router';
import { NewSubscription, TemplateEditor } from './forms';
import { SubscriptionDetail, SubscriptionList, TemplateList } from './pages';
import './subscriptions.css';

export function getRoutes(): RouteObject[] {
  return [
    { path: '/subscriptions', element: <SubscriptionList /> },
    { path: '/subscriptions/new', element: <NewSubscription /> },
    { path: '/subscriptions/templates', element: <TemplateList /> },
    { path: '/subscriptions/templates/new', element: <TemplateEditor /> },
    { path: '/subscriptions/templates/:id/edit', element: <TemplateEditor /> },
    { path: '/subscriptions/:id', element: <SubscriptionDetail /> },
  ];
}

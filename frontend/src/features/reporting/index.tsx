import type { RouteObject } from 'react-router'
import { FeaturePlaceholder } from '../../app/FeaturePlaceholder'

export function getRoutes(): RouteObject[] {
  return [{ path: '/overview', element: <FeaturePlaceholder title="Overview" description="A clear view of your subscription business." /> }]
}

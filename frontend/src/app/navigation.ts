import { CircleAlert, CircleUserRound, CreditCard, FileText, Home, Layers3, Package, PanelsTopLeft, Percent, Settings2, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Role } from '../lib'

export type NavigationItem = { label: string; to: string; icon: LucideIcon; roles?: readonly Role[] }
const staffNavigation: NavigationItem[] = [
  { label: 'Overview', to: '/overview', icon: Home },
  { label: 'CycleGuard', to: '/cycleguard', icon: CircleAlert },
  { label: 'Customers', to: '/customers', icon: Users },
  { label: 'Products', to: '/catalog/products', icon: Package },
  { label: 'Plans', to: '/catalog/plans', icon: Layers3 },
  { label: 'Subscriptions', to: '/subscriptions', icon: PanelsTopLeft },
  { label: 'Quotation templates', to: '/subscriptions/templates', icon: FileText },
  { label: 'Invoices', to: '/billing/invoices', icon: CreditCard },
  { label: 'Taxes', to: '/billing/taxes', icon: Percent },
  { label: 'Discounts', to: '/billing/discounts', icon: Percent },
  { label: 'Staff settings', to: '/settings/staff', icon: Settings2, roles: ['ADMIN'] },
]
const customerNavigation: NavigationItem[] = [
  { label: 'My subscriptions', to: '/portal/subscriptions', icon: PanelsTopLeft },
  { label: 'My invoices', to: '/portal/invoices', icon: CreditCard },
  { label: 'Account', to: '/portal/account', icon: CircleUserRound },
]

export function getNavigation(role: Role): NavigationItem[] {
  return (role === 'CUSTOMER' ? customerNavigation : staffNavigation).filter(item => !item.roles || item.roles.includes(role))
}

export function currentNavigation(items: NavigationItem[], pathname: string): NavigationItem | undefined {
  return [...items].sort((a, b) => b.to.length - a.to.length).find(item => pathname === item.to || pathname.startsWith(`${item.to}/`))
}

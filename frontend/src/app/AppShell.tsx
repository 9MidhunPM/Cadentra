import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { ArrowUpRight, ChartNoAxesCombined, ChevronRight, CircleUserRound, CreditCard, Layers3, LifeBuoy, LogOut, Menu, Package, PanelsTopLeft, Settings2, Users, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useSession, getErrorMessage } from '../lib'

type NavItem = { label: string; to: string; icon: LucideIcon; adminOnly?: boolean }
const staffNavigation: NavItem[] = [
  { label: 'Overview', to: '/overview', icon: ChartNoAxesCombined },
  { label: 'Customers', to: '/customers', icon: Users },
  { label: 'Products', to: '/catalog/products', icon: Package },
  { label: 'Plans', to: '/catalog/plans', icon: Layers3 },
  { label: 'Subscriptions', to: '/subscriptions', icon: PanelsTopLeft },
  { label: 'Quotation templates', to: '/subscriptions/templates', icon: Layers3 },
  { label: 'Invoices', to: '/billing/invoices', icon: CreditCard },
  { label: 'Taxes', to: '/billing/taxes', icon: Settings2 },
  { label: 'Discounts', to: '/billing/discounts', icon: Package },
  { label: 'Staff settings', to: '/settings/staff', icon: Settings2, adminOnly: true },
]
const customerNavigation: NavItem[] = [
  { label: 'My subscriptions', to: '/portal/subscriptions', icon: PanelsTopLeft },
  { label: 'My invoices', to: '/portal/invoices', icon: CreditCard },
  { label: 'Account', to: '/portal/account', icon: CircleUserRound },
]

export function AppShell() {
  const { actor, logout } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const sidebar = useRef<HTMLElement>(null)
  const location = useLocation()
  const customer = actor?.role === 'CUSTOMER'
  const items = (customer ? customerNavigation : staffNavigation).filter(item => !item.adminOnly || actor?.role === 'ADMIN')
  const current = items.find(item => location.pathname === item.to || (item.to !== '/subscriptions' && location.pathname.startsWith(`${item.to}/`)))

  useEffect(() => {
    const media = window.matchMedia('(max-width: 700px)')
    const closeOnResize = () => { if (!media.matches) setMenuOpen(false) }
    media.addEventListener('change', closeOnResize)
    return () => media.removeEventListener('change', closeOnResize)
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = () => Array.from(sidebar.current?.querySelectorAll<HTMLElement>('a[href],button:not([disabled])') || [])
    focusable()[0]?.focus()
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); setMenuOpen(false) }
      if (event.key === 'Tab') {
        const items = focusable()
        const first = items[0]
        const last = items.at(-1)
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', handleKey); previous?.focus() }
  }, [menuOpen])

  async function signOut() {
    setSigningOut(true)
    setLogoutError(null)
    try { await logout() } catch (error) { setLogoutError(getErrorMessage(error)) } finally { setSigningOut(false) }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      {menuOpen ? <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMenuOpen(false)} /> : null}
      <aside ref={sidebar} id="workspace-sidebar" className={`sidebar ${menuOpen ? 'is-open' : ''}`} role={menuOpen ? 'dialog' : undefined} aria-modal={menuOpen || undefined} aria-label="Workspace sidebar">
        <div className="brand-row">
          <NavLink to="/" className="wordmark" onClick={() => setMenuOpen(false)} aria-label="Cadentra home"><span className="brand-symbol" aria-hidden="true"><Layers3 size={24} /></span>Cadentra<span className="wordmark-dot">.</span></NavLink>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={20} /></button>
        </div>
        <div className="organisation"><span className="organisation-avatar">B</span><div><strong>Brightloop Software</strong><span>{customer ? 'Customer portal' : 'Subscription operations'}</span></div></div>
        <nav aria-label={customer ? 'Customer navigation' : 'Main navigation'}>
          <p className="nav-section-label">{customer ? 'YOUR ACCOUNT' : 'WORKSPACE'}</p>
          {items.map(({ label, to, icon: Icon }) => <NavLink key={to} to={to} end={to === '/subscriptions'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} onClick={() => setMenuOpen(false)}><Icon size={19} aria-hidden="true" /><span>{label}</span></NavLink>)}
        </nav>
        <div className="sidebar-footer"><LifeBuoy size={18} aria-hidden="true" /><p>Every subscription.<br />Every cycle. Accounted for.</p></div>
      </aside>
      <div className="main-column" inert={menuOpen}>
        <header className="topbar">
          <div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Open navigation" aria-controls="workspace-sidebar" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={22} /></button><span>{customer ? 'Customer portal' : 'Workspace'}</span><ChevronRight size={15} aria-hidden="true" /><strong>{current?.label || 'Details'}</strong></div>
          <div className="account-menu"><span className="account-avatar" aria-hidden="true">{actor?.name?.slice(0, 1).toUpperCase() || 'U'}</span><span className="account-name">{actor?.name}<small>{actor?.role.toLowerCase()}</small></span><button className="icon-button" aria-label={signingOut ? 'Signing out' : 'Sign out'} disabled={signingOut} onClick={signOut}><LogOut size={18} /></button></div>
        </header>
        {logoutError ? <div className="shell-error" role="alert">{logoutError}</div> : null}
        <main id="main-content" className="main-content" tabIndex={-1}><Outlet /></main>
        <footer className="workspace-footer"><span>Cadentra · Brightloop Software</span><span>Every cycle, accounted for <ArrowUpRight size={13} aria-hidden="true" /></span></footer>
      </div>
    </div>
  )
}

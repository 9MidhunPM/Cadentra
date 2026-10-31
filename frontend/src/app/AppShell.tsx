import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { AnimatePresence, LayoutGroup, m as motion, useAnimationControls, useReducedMotion } from 'motion/react'
import { ArrowUpRight, ChevronRight, LogOut, Menu, Moon, RotateCcw, Sun, X } from 'lucide-react'
import { useSession, getErrorMessage } from '../lib'
import { currentNavigation, getNavigation } from './navigation'
import { PageSearch } from './PageSearch'
import { useTheme } from './theme'

export function AppShell() {
  const { actor, logout } = useSession()
  const { theme, toggleTheme } = useTheme()
  const reduceMotion = useReducedMotion()
  const [menuOpen, setMenuOpen] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches)
  const [signingOut, setSigningOut] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const sidebar = useRef<HTMLElement>(null)
  const menuTrigger = useRef<HTMLButtonElement>(null)
  const location = useLocation()
  const routeArrival = useAnimationControls()
  const previousPath = useRef(location.pathname)
  const customer = actor?.role === 'CUSTOMER'
  const items = getNavigation(actor?.role || 'CUSTOMER')
  const current = currentNavigation(items, location.pathname)

  useEffect(() => {
    // Keep the existing Outlet/main mounted: filtering, data reloads and form state
    // are not animation triggers. The initial page load is deliberately immediate.
    if (reduceMotion) {
      previousPath.current = location.pathname
      routeArrival.set({ opacity: 1, y: 0 })
      return
    }
    if (previousPath.current === location.pathname) return
    previousPath.current = location.pathname
    routeArrival.set({ opacity: .65, y: 6 })
    void routeArrival.start({ opacity: 1, y: 0, transition: { duration: .2, ease: [.16, 1, .3, 1] } })
    return () => routeArrival.stop()
  }, [location.pathname, reduceMotion, routeArrival])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)')
    const resize = () => { setMobile(media.matches); if (!media.matches) setMenuOpen(false) }
    media.addEventListener('change', resize)
    return () => media.removeEventListener('change', resize)
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const previous = menuTrigger.current || (document.activeElement instanceof HTMLElement ? document.activeElement : null)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = () => Array.from(sidebar.current?.querySelectorAll<HTMLElement>('a[href],button:not([disabled])') || [])
    focusable()[0]?.focus()
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); setMenuOpen(false) }
      if (event.key === 'Tab') {
        const elements = focusable()
        const first = elements[0]
        const last = elements.at(-1)
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
      <header className="topbar" inert={menuOpen}>
        <div className="brand-row"><NavLink to="/app" className="wordmark" aria-label="Cadentra home"><span className="brand-symbol" aria-hidden="true">C</span><span>Cadentra<small>Brightloop Software</small></span></NavLink></div>
        <div className="toolbar-content">
          <button ref={menuTrigger} className="icon-button mobile-menu" aria-label="Open navigation" aria-controls="workspace-sidebar" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={22} /></button>
          <PageSearch items={items} disabled={menuOpen} />
          <div className="account-menu">
            <motion.button type="button" className="icon-button theme-toggle" whileTap={{ scale: .9 }} onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}><AnimatePresence mode="wait" initial={false}><motion.span key={theme} initial={{ opacity: 0, rotate: -60 }} animate={{ opacity: 1, rotate: 0 }} exit={{ opacity: 0, rotate: 60 }} transition={{ duration: .12 }}>{theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}</motion.span></AnimatePresence></motion.button>
            <span className="account-avatar" aria-hidden="true">{actor?.name?.slice(0, 1).toUpperCase() || 'U'}</span><span className="account-name">{actor?.name}<small>{actor?.role.toLowerCase()}</small></span>
            <button className="icon-button" aria-label={signingOut ? 'Signing out' : 'Sign out'} disabled={signingOut} onClick={signOut}><LogOut size={18} /></button>
          </div>
        </div>
      </header>
      <div className="workspace-body">
        <div style={{ display: 'contents' }} inert={mobile && !menuOpen} aria-hidden={mobile && !menuOpen || undefined}><AnimatePresence initial={false}>
          {mobile && menuOpen ? <motion.button key="backdrop" className="nav-backdrop" aria-label="Close navigation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .15 }} onClick={() => setMenuOpen(false)} /> : null}
          {!mobile || menuOpen ? <motion.aside key="sidebar" ref={sidebar} id="workspace-sidebar" className="sidebar" initial={mobile && !reduceMotion ? { x: '-100%' } : false} animate={{ x: 0 }} exit={mobile && !reduceMotion ? { x: '-100%' } : { opacity: 0 }} transition={{ type: 'spring', stiffness: 420, damping: 38 }} role={mobile ? 'dialog' : undefined} aria-modal={mobile || undefined} aria-label="Workspace sidebar">
            <div className="workspace-identity"><span className="organisation-avatar">B</span><span><strong>Brightloop Software</strong><small>{customer ? 'Your customer account' : 'Subscription operations'}</small></span><button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={19} /></button></div>
            <LayoutGroup id={`workspace-${actor?.role}`}><nav aria-label={customer ? 'Customer navigation' : 'Main navigation'}>{items.map(({ label, to, icon: Icon }) => <NavLink key={to} to={to} end={to === '/subscriptions'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} onClick={() => setMenuOpen(false)}>{({ isActive }) => <>{isActive ? <motion.span className="nav-active-surface" layoutId="active-navigation" transition={{ type: 'spring', stiffness: 480, damping: 38 }} /> : null}<Icon size={19} aria-hidden="true" /><span>{label}</span></>}</NavLink>)}</nav></LayoutGroup>
            <div className="sidebar-footer"><RotateCcw size={18} className="sidebar-cycle" aria-hidden="true" /><p>Every subscription.<br />Every cycle. Accounted for.</p></div>
          </motion.aside> : null}
        </AnimatePresence></div>
        <div className="main-column" inert={menuOpen}>
          {logoutError ? <div className="shell-error" role="alert">{logoutError}</div> : null}
          <div className="breadcrumb"><span>{customer ? 'Customer portal' : 'Workspace'}</span><ChevronRight size={13} aria-hidden="true" /><strong>{current?.label || 'Details'}</strong><span className="theme-caption">{theme === 'dark' ? 'Graphite Mint' : 'Sage Commerce'}</span></div>
          <main id="main-content" className="main-content" tabIndex={-1}><motion.div initial={false} animate={routeArrival}><Outlet /></motion.div></main>
          <footer className="workspace-footer"><span>Cadentra · Brightloop Software</span><span>Every cycle, accounted for <ArrowUpRight size={13} aria-hidden="true" /></span></footer>
        </div>
      </div>
    </div>
  )
}

import { useEffect } from 'react'
import { useLocation } from 'react-router'
import { useSession } from '../lib'

/** Announce route changes without moving focus during filtering/query updates. */
export function PageNavigation() {
  const { pathname } = useLocation()
  const { status } = useSession()

  useEffect(() => {
    if (status === 'loading') return
    const frame = window.requestAnimationFrame(() => {
      const heading = document.querySelector<HTMLElement>('h1')
      document.title = heading?.textContent ? `${heading.textContent} · Cadentra` : 'Cadentra'
      const target = heading || document.querySelector<HTMLElement>('main')
      if (target) {
        target.setAttribute('tabindex', '-1')
        target.focus({ preventScroll: true })
      }
    })
    return () => window.cancelAnimationFrame(frame)
  }, [pathname, status])

  return null
}

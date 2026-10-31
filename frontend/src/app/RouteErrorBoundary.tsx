import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

/** Never render thrown values, route-loader payloads or stack traces to users. */
export function RouteErrorBoundary() {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    document.title = 'Page unavailable · Cadentra'
    heading.current?.focus()
  }, [])

  return (
    <main className="standalone-page">
      <h1 ref={heading} tabIndex={-1}>We couldn’t open this page</h1>
      <p>Please try loading it again, or return to your workspace.</p>
      <button className="primary-button" onClick={() => window.location.reload()}>Reload page</button>
      <p><Link to="/">Return to your workspace</Link></p>
    </main>
  )
}

import { Construction } from 'lucide-react'
import { Link } from 'react-router'

/** Bootstrap-only boundary. Feature owners replace their own route elements. */
export function FeaturePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <section className="feature-placeholder" aria-labelledby="page-title">
      <div className="page-heading">
        <h1 id="page-title">{title}</h1>
        <p>{description}</p>
      </div>
      <div className="placeholder-body">
        <div className="placeholder-symbol"><Construction size={28} aria-hidden="true" /></div>
        <h2>This workspace is taking shape</h2>
        <p>This feature is not implemented yet. Your records will appear here when it is connected.</p>
        <span className="implementation-label">Not implemented</span>
      </div>
    </section>
  )
}

export function NotFound() {
  return <div className="standalone-page"><h1>Page not found</h1><p>The page may have moved, or the address may be incorrect.</p><Link to="/">Return to Cadentra</Link></div>
}

import { useId, useLayoutEffect, useRef, useState } from 'react'
import { DateLabel, Money } from '../../components/ui'
import type { RevenueSeries } from './types'

export function RevenueChart({ series }: { series: RevenueSeries }) {
  const [showData, setShowData] = useState(false)
  const id = useId()
  const container = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(600)
  useLayoutEffect(() => {
    const element = container.current
    if (!element) return
    const measure = () => {
      const measured = element.getBoundingClientRect().width
      if (Number.isFinite(measured) && measured > 0) setWidth(Math.max(160, Math.round(measured)))
    }
    measure()
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(measure)
      observer.observe(element)
      return () => observer.disconnect()
    }
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])
  const left = 44
  const right = width - 16
  const compactDate = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  const dateLabel = (value: string) => width < 480 ? compactDate.format(new Date(`${value}T00:00:00Z`)) : value
  // Numbers are used only to map server values to visual coordinates. All displayed
  // financial values remain the API's exact decimal strings; no totals are computed.
  const max = Math.max(1, ...series.buckets.flatMap(bucket => [Number(bucket.invoiced_gross), Number(bucket.cash_received)]))
  const x = (index: number) => left + index * (right - left) / Math.max(series.buckets.length - 1, 1)
  const y = (value: string) => 210 - Number(value) / max * 175
  const path = (key: 'invoiced_gross' | 'cash_received') => series.buckets.map((bucket, index) => `${index ? 'L' : 'M'}${x(index)},${y(bucket[key])}`).join(' ')
  const axisLabel = new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 })
  const markerRadius = series.buckets.length > 90 ? 1.5 : 3
  return <><div className="report-chart-legend"><span><i className="report-legend-invoiced" />Invoiced ({series.currency})</span><span><i className="report-legend-received" />Received ({series.currency})</span></div>
    <div ref={container}>{series.buckets.length ? <svg className="report-chart" style={{ height: 250 }} viewBox={`0 0 ${width} 250`} role="img" aria-labelledby={`${id}-title ${id}-desc`}><title id={`${id}-title`}>Invoiced and received</title><desc id={`${id}-desc`}>Recorded invoice and payment amounts for the selected date range. The axis is approximate; use View chart data for exact amounts.</desc>{Array.from({ length: 5 }, (_, index) => {
      const line = 35 + index * 175 / 4
      return <g key={index}><line x1={left} x2={right} y1={line} y2={line} className="report-chart-grid" /><text style={{ fontSize: 12 }} x={left - 8} y={line + 4} textAnchor="end">{axisLabel.format(max * (4 - index) / 4)}</text></g>
    })}<path d={path('invoiced_gross')} className="report-line-invoiced" /><path d={path('cash_received')} className="report-line-received" />{series.buckets.map((bucket, index) => <g key={bucket.period_start}><title>{`${bucket.period_start} to ${bucket.period_end} (exclusive): invoiced ${series.currency} ${bucket.invoiced_gross}; received ${series.currency} ${bucket.cash_received}`}</title><circle cx={x(index)} cy={y(bucket.invoiced_gross)} r={markerRadius} className="report-dot-invoiced" /><circle cx={x(index)} cy={y(bucket.cash_received)} r={markerRadius} className="report-dot-received" /></g>)}<text style={{ fontSize: 12 }} x={left} y="240">{dateLabel(series.range_from)}</text><text style={{ fontSize: 12 }} x={right} y="240" textAnchor="end">{dateLabel(series.range_to)} {width < 480 ? '(excl.)' : '(exclusive)'}</text></svg> : <p className="report-series-empty">No reporting buckets in this range.</p>}</div>
    <button type="button" className="report-text-button" aria-expanded={showData} aria-controls={`${id}-table`} onClick={() => setShowData(value => !value)}>{showData ? 'Hide chart data' : 'View chart data'}</button>
    {showData ? <div className="report-chart-data" id={`${id}-table`} tabIndex={0} role="region" aria-label="Chart data"><table><caption className="ui-sr-only">Exact reporting amounts</caption><thead><tr><th>Period starts</th><th>Ends before</th><th>Invoiced</th><th>Received</th></tr></thead><tbody>{series.buckets.map(bucket => <tr key={bucket.period_start}><td><DateLabel value={bucket.period_start} /></td><td><DateLabel value={bucket.period_end} /></td><td><Money amount={bucket.invoiced_gross} currency={series.currency} /></td><td><Money amount={bucket.cash_received} currency={series.currency} /></td></tr>)}</tbody></table></div> : null}
  </>
}

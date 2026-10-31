import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Search, Users } from 'lucide-react'
import { apiClient, getErrorMessage, isAbortError } from '../../lib'
import type { ListResponse } from '../../lib'
import type { Customer } from './types'

export function CustomerFilter({ selectedId, selectedName, onChange }: { selectedId: string; selectedName: string; onChange: (id: string, name: string) => void }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (!open) return
    input.current?.focus()
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true); setError(null)
      const params = new URLSearchParams({ q: query, page: '1', page_size: '25' })
      apiClient.request<ListResponse<Customer>>(`/customers?${params}`, { signal: controller.signal }).then(result => {
        if (!controller.signal.aborted) { setItems(result.items); setTotal(result.total); setActive(0) }
      }).catch(error => { if (!controller.signal.aborted && !isAbortError(error)) setError(getErrorMessage(error)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 180)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [open, query])
  useEffect(() => {
    if (open) document.getElementById(`report-customer-${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [open, active, items])
  function select(id: string, name: string) { onChange(id, name); setOpen(false); trigger.current?.focus() }
  return <div className="report-customer" ref={root} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false) }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus() } }}>
    <button ref={trigger} type="button" className="report-filter-button" aria-expanded={open} aria-controls="report-customer-results" onClick={() => { if (!open) { setLoading(true); setError(null); setItems([]) } setOpen(value => !value) }}><Users size={16} aria-hidden="true" /><span>{selectedId ? selectedName : 'All customers'}</span><ChevronDown size={14} aria-hidden="true" /></button>
    {open ? <div className="report-customer-popover"><div className="report-customer-search"><Search size={16} aria-hidden="true" /><input ref={input} aria-label="Find a customer" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="report-customer-results" aria-activedescendant={!loading && items[active] ? `report-customer-${active}` : undefined} value={query} placeholder="Search name or email" onChange={event => { setQuery(event.target.value); setItems([]); setLoading(true) }} onKeyDown={event => {
      if (event.key === 'ArrowDown') { event.preventDefault(); setActive(index => (index + 1) % Math.max(items.length, 1)) }
      if (event.key === 'ArrowUp') { event.preventDefault(); setActive(index => (index - 1 + items.length) % Math.max(items.length, 1)) }
      if (event.key === 'Enter') {
        event.preventDefault()
        if (items[active] && !loading) select(items[active].id, items[active].display_name)
      }
    }} /></div><button type="button" className="report-all-customers" onClick={() => select('', '')}>All customers</button>
    {loading ? <p role="status">Searching customers…</p> : error ? <p role="alert">{error}</p> : <div id="report-customer-results" role="listbox" aria-label="Customers">{items.map((item, index) => <button type="button" tabIndex={-1} role="option" aria-selected={index === active} id={`report-customer-${index}`} key={item.id} onMouseMove={() => setActive(index)} onClick={() => select(item.id, item.display_name)}><strong>{item.display_name}</strong><small>{item.email}</small></button>)}</div>}
    {!loading && !error && !items.length ? <p role="status">No matching customers.</p> : null}{!loading && !error && total > items.length ? <p className="report-filter-help">Showing the first 25 matches. Refine your search.</p> : null}</div> : null}
  </div>
}

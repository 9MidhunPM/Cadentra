import { useEffect, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { ArrowRight, Search, X } from 'lucide-react'
import { useNavigate } from 'react-router'
import type { NavigationItem } from './navigation'

export function PageSearch({ items, disabled = false }: { items: NavigationItem[]; disabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const chosen = useRef(false)
  const results = items.filter(item => item.label.toLowerCase().includes(query.trim().toLowerCase()))

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        if (disabled) return
        setOpen(current => !current)
        setQuery('')
        setActiveIndex(0)
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [disabled])

  useEffect(() => {
    if (open) document.getElementById(`page-result-${activeIndex}`)?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex, query])

  function choose(item: NavigationItem) {
    chosen.current = true
    navigate(item.to)
    setOpen(false)
  }

  return (
    <Dialog.Root open={open} onOpenChange={value => { setOpen(value); setQuery(''); setActiveIndex(0) }}>
      <Dialog.Trigger className="page-search-trigger" aria-label="Search pages" disabled={disabled}><Search size={18} aria-hidden="true" /><span>Search pages</span><kbd>Ctrl K</kbd></Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="search-overlay" />
        <Dialog.Content className="page-search-dialog" onOpenAutoFocus={event => { event.preventDefault(); input.current?.focus() }} onCloseAutoFocus={event => {
          if (chosen.current) {
            event.preventDefault()
            chosen.current = false
            window.requestAnimationFrame(() => {
              const heading = document.querySelector<HTMLElement>('h1')
              heading?.setAttribute('tabindex', '-1')
              heading?.focus({ preventScroll: true })
            })
          }
        }}>
          <Dialog.Title className="sr-only">Search pages</Dialog.Title>
          <Dialog.Description className="sr-only">Find a page in your workspace. Use the arrow keys to choose a result and Enter to open it.</Dialog.Description>
          <div className="page-search-field"><Search size={20} aria-hidden="true" /><input ref={input} aria-label="Search pages" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="page-search-results" aria-activedescendant={results[activeIndex] ? `page-result-${activeIndex}` : undefined} placeholder="Where would you like to go?" value={query} onChange={event => { setQuery(event.target.value); setActiveIndex(0) }} onKeyDown={event => {
            if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex(index => (index + 1) % Math.max(results.length, 1)) }
            if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex(index => (index - 1 + results.length) % Math.max(results.length, 1)) }
            if (event.key === 'Enter' && results[activeIndex]) { event.preventDefault(); choose(results[activeIndex]) }
          }} /><Dialog.Close className="icon-button" aria-label="Close page search"><X size={18} /></Dialog.Close></div>
          <div className="page-search-results" id="page-search-results" role="listbox" aria-label="Pages">
            {results.map((item, index) => <button type="button" role="option" aria-selected={index === activeIndex} tabIndex={-1} id={`page-result-${index}`} key={item.to} className="page-search-result" onMouseMove={() => setActiveIndex(index)} onClick={() => choose(item)}><item.icon size={19} aria-hidden="true" /><span>{item.label}</span><ArrowRight size={16} aria-hidden="true" /></button>)}
          </div>
          {results.length === 0 ? <p className="search-no-results" role="status">No matching pages. Try a different name.</p> : null}
          <div className="page-search-help"><span>Searches pages available to your account</span><span><kbd>↑</kbd><kbd>↓</kbd> navigate <kbd>↵</kbd> open</span></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

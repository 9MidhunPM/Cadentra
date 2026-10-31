import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowDown, ArrowRight, Check, CircleCheck, CreditCard, FileText, Layers3, RefreshCw, ShieldCheck } from 'lucide-react'
import './home.css'

type Stage = 'plan' | 'quote' | 'bill' | 'renew'
const stages: { id: Stage; label: string; number: string; title: string; description: string }[] = [
  { id: 'plan', label: 'Plan', number: '01', title: 'Set the terms. Keep the flexibility.', description: 'Bring products, variants and recurring plans together. Choose the cadence, quantities and policies that fit the service.' },
  { id: 'quote', label: 'Quote', number: '02', title: 'Start with a clear agreement.', description: 'Turn a plan into a quotation, with the customer, dates and line items in view. Confirm the terms before a subscription becomes active.' },
  { id: 'bill', label: 'Bill', number: '03', title: 'Make every amount explainable.', description: 'Connect recurring invoices, discounts, taxes and recorded payments. See what was billed, what was paid and what remains.' },
  { id: 'renew', label: 'Renew', number: '04', title: 'Let the next chapter follow naturally.', description: 'Keep pause, close and renewal actions connected to the original subscription. A renewal starts a linked draft, with a history you can follow.' },
]
const people = [
  { name: 'Midhun P M', initials: 'MP', role: 'Platform & coordination', description: 'The foundation that connects the whole workspace.' },
  { name: 'Thanushree Suresh', initials: 'TS', role: 'Subscription workflows', description: 'The journey from first quotation to next renewal.' },
  { name: 'Noel Biju', initials: 'NB', role: 'Billing & payments', description: 'The numbers, invoices and payment records behind each cycle.' },
  { name: 'Sherin Saji', initials: 'SS', role: 'Experience & reporting', description: 'A clear view for the team and the customer.' },
]

function StagePreview({ stage }: { stage: Stage }) {
  return <div className="home-preview" aria-label={`${stage} illustrative product preview`}>
    <div className="home-preview-toolbar"><span className="home-mini-brand"><Layers3 size={18} aria-hidden="true" />Cadentra</span><span>Brightloop Software</span><span className="home-preview-avatar">B</span></div>
    <div className="home-preview-layout"><aside className="home-preview-sidebar" aria-hidden="true"><Layers3 size={18} /><FileText size={18} /><CreditCard size={18} /><RefreshCw size={18} /></aside><div className="home-preview-content">
      <div className="home-preview-heading"><div><p className="home-preview-kicker">{stage === 'plan' ? 'CATALOG / PLANS' : stage === 'bill' ? 'BILLING / INVOICES' : 'WORKSPACE / SUBSCRIPTIONS'}</p><h3>{stage === 'plan' ? 'A plan for every cycle.' : stage === 'quote' ? 'A clear starting point.' : stage === 'bill' ? 'Every number, connected.' : 'Ready for what’s next.'}</h3></div><span className="home-preview-dot" /></div>
      {stage === 'plan' && <><div className="home-plan-name"><span className="home-preview-icon"><Layers3 size={22} aria-hidden="true" /></span><div><strong>Design Suite</strong><span>Monthly subscription plan</span></div><span className="home-label">MONTHLY</span></div><dl className="home-preview-grid"><div><dt>Product price</dt><dd>INR 1,000.00</dd></div><div><dt>Premium variant</dt><dd>+ INR 560.00</dd></div><div><dt>Per-cycle base fee</dt><dd>INR 0.00</dd></div><div><dt>Minimum quantity</dt><dd>3 seats</dd></div></dl><div className="home-policy-list"><span><Check size={13} aria-hidden="true" />Pause allowed</span><span><Check size={13} aria-hidden="true" />Renewal allowed</span><span><Check size={13} aria-hidden="true" />Automatic closure</span></div><div className="home-preview-total"><span>Three seats · before tax and discounts</span><strong>INR 4,680.00<span> / cycle</span></strong></div></>}
      {stage === 'quote' && <><div className="home-document-heading"><div><span className="home-label">QUOTATION</span><h4>Design Suite · 3 seats</h4><p>Prepared for the customer</p></div><FileText size={28} aria-hidden="true" /></div><div className="home-preview-row"><span>Product + premium variant</span><strong>INR 1,560.00 × 3</strong></div><div className="home-preview-row"><span>Billing cadence</span><strong>Monthly</strong></div><div className="home-preview-row"><span>Agreed product subtotal</span><strong>INR 4,680.00</strong></div><div className="home-stage-track"><span>Draft</span><i /><strong>Quotation</strong><i /><span>Confirmed</span><i /><span>Active</span></div><p className="home-preview-footnote">Review the agreed terms. Confirm before activation.</p></>}
      {stage === 'bill' && <><div className="home-document-heading"><div><span className="home-label">CONFIRMED</span><h4>Design Suite invoice</h4><p>One service period. One stored calculation.</p></div><FileText size={28} aria-hidden="true" /></div><div className="home-preview-row"><span>Product subtotal</span><strong>INR 4,680.00</strong></div><div className="home-preview-row"><span>Eligible discount · 10%</span><strong>− INR 468.00</strong></div><div className="home-preview-row"><span>Illustrative tax · 18%</span><strong>INR 758.16</strong></div><div className="home-preview-total"><span>Invoice total</span><strong>INR 4,970.16</strong></div><div className="home-payment-strip"><CircleCheck size={17} aria-hidden="true" /><span>Recorded payment <strong>INR 2,000.00</strong></span><span>Balance <strong>INR 2,970.16</strong></span></div></>}
      {stage === 'renew' && <><div className="home-renew-card"><span className="home-renew-icon"><RefreshCw size={28} aria-hidden="true" /></span><span className="home-label">NEXT TERM</span><h4>A new cycle.<br />The same clear history.</h4><p>Renewal creates a linked draft, ready for the next quotation and confirmation.</p></div><div className="home-renew-link"><div><small>ORIGINAL SUBSCRIPTION</small><strong>Design Suite</strong><span className="home-label">CLOSED</span></div><ArrowRight size={23} aria-hidden="true" /><div><small>LINKED RENEWAL</small><strong>Design Suite</strong><span className="home-label">DRAFT</span></div></div></>}
    </div></div><div className="home-preview-footer"><span>Illustrative product preview</span><span>Amounts shown in INR</span></div>
  </div>
}

export default function HomePage() {
  const [stage, setStage] = useState<Stage>('plan')
  const [filmFailed, setFilmFailed] = useState(false)
  const [staticFilm, setStaticFilm] = useState(() => {
    const connection = (navigator as Navigator & { connection?: EventTarget & { saveData?: boolean } }).connection
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches || connection?.saveData === true
  })
  const [showExplore, setShowExplore] = useState(false)
  const menu = useRef<HTMLDetailsElement>(null)
  const film = useRef<HTMLVideoElement>(null)
  const hero = useRef<HTMLElement>(null)
  useEffect(() => {
    const dismissOutside = (event: PointerEvent) => {
      const details = menu.current
      if (details?.open && event.target instanceof Node && !details.contains(event.target)) details.open = false
    }
    const dismissEscape = (event: globalThis.KeyboardEvent) => {
      const details = menu.current
      if (event.key === 'Escape' && details?.open) {
        details.open = false
        details.querySelector<HTMLElement>('summary')?.focus()
      }
    }
    document.addEventListener('pointerdown', dismissOutside)
    document.addEventListener('keydown', dismissEscape)
    return () => {
      document.removeEventListener('pointerdown', dismissOutside)
      document.removeEventListener('keydown', dismissEscape)
    }
  }, [])
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const connection = (navigator as Navigator & { connection?: EventTarget & { saveData?: boolean } }).connection
    const update = () => setStaticFilm(media.matches || connection?.saveData === true)
    media.addEventListener('change', update)
    connection?.addEventListener('change', update)
    return () => { media.removeEventListener('change', update); connection?.removeEventListener('change', update) }
  }, [])
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const video = film.current
    const section = hero.current
    if (!video || !section) return
    let frame = 0
    let position: number | undefined
    let previousTime = 0
    const update = (now: number) => {
      frame = 0
      if (!Number.isFinite(video.duration) || video.duration <= 0) return
      const distance = Math.max(1, section.offsetHeight - window.innerHeight)
      const progress = media.matches ? 0 : Math.max(0, Math.min(1, -section.getBoundingClientRect().top / distance))
      setShowExplore(media.matches || progress >= 0.8)
      const target = progress * Math.max(0, video.duration - 1 / 60)
      const elapsed = previousTime ? Math.min(now - previousTime, 64) : 16
      previousTime = now
      position = position === undefined || media.matches ? target : position + (target - position) * (1 - Math.exp(-elapsed / 80))
      if (Math.abs(target - position) < 0.008) position = target
      if (Math.abs(video.currentTime - position) > 0.004) video.currentTime = position
      if (position !== target) frame = requestAnimationFrame(update)
      else previousTime = 0
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
    video.pause()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    video.addEventListener('loadedmetadata', schedule)
    media.addEventListener('change', schedule)
    schedule()
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      video.removeEventListener('loadedmetadata', schedule)
      media.removeEventListener('change', schedule)
      cancelAnimationFrame(frame)
    }
  }, [filmFailed, staticFilm])
  const page = useRef<HTMLElement>(null)
  const tabs = useRef<(HTMLButtonElement | null)[]>([])
  const current = stages.find(item => item.id === stage)!
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) { entry.target.classList.add('home-revealed'); observer.unobserve(entry.target) }
    }, { threshold: 0.08 })
    const elements = page.current?.querySelectorAll('.home-section-heading, .home-product-stage, .home-cycle-copy, .home-health-panel, .home-team-heading, .home-people article, .home-final-cta')
    elements?.forEach(element => { element.classList.add('home-reveal'); observer.observe(element) })
    return () => { observer.disconnect(); elements?.forEach(element => element.classList.remove('home-reveal')) }
  }, [])
  function tabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number | undefined
    if (event.key === 'ArrowRight') next = (index + 1) % stages.length
    if (event.key === 'ArrowLeft') next = (index + stages.length - 1) % stages.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = stages.length - 1
    if (next !== undefined) { event.preventDefault(); setStage(stages[next].id); tabs.current[next]?.focus() }
  }
  return <main ref={page} className="home-page">
    <section id="top" ref={hero} className={filmFailed || staticFilm ? 'home-hero home-hero-static' : 'home-hero'} aria-labelledby="home-title">
      <div className="home-film-sticky">
      <h1 id="home-title" className="home-film-title">Cadentra: every cycle under control</h1>
      <a className="home-skip" href="#product">Skip to content</a>
      <div id="home-content" className="home-film-stage" tabIndex={-1}>
        {filmFailed || staticFilm ? <img src="/assets/home/hero.webp" alt="Mint glass sculpture" /> : <video ref={film} src="/assets/home/hero-film.mp4" poster="/assets/home/hero.webp" aria-label="Cadentra concept film" muted playsInline preload="auto" onError={() => setFilmFailed(true)} />}
      </div>
      <header className="home-film-header">
        <a className="home-film-brand" href="#top">Cadentra<span>.</span></a>
        <nav className="home-film-nav" aria-label="Main navigation"><a href="#top">Home</a><a href="#product">Product</a><a href="#cycleguard">CycleGuard</a><a href="#team">Our team</a></nav>
        <a className="home-film-app" href="/app">Open app <ArrowRight size={15} aria-hidden="true" /></a>
        <details className="home-film-menu" ref={menu}><summary aria-label="Main navigation">Menu</summary><nav aria-label="Mobile navigation" onClick={() => { if (menu.current) menu.current.open = false }}><a href="#top">Home</a><a href="#product">Product</a><a href="#cycleguard">CycleGuard</a><a href="#team">Our team</a><a href="/app">Open app</a></nav></details>
      </header>
      <p className="home-film-mobile-copy" aria-hidden="true">Every cycle.<br />Under control.</p>
      {!filmFailed && !staticFilm && !showExplore && <span className="home-film-scroll-cue" aria-hidden="true">Scroll to explore <ArrowDown size={14} /></span>}
      {(showExplore || filmFailed || staticFilm) && <a className="home-film-explore" href="#product">Explore the product <ArrowDown size={15} aria-hidden="true" /></a>}
      </div>
    </section>
    <section className="home-product home-section" id="product" tabIndex={-1} aria-labelledby="home-product-title"><div className="home-section-heading"><p className="home-section-kicker">ONE CONTINUOUS WORKFLOW</p><h2 id="home-product-title">From first quote to next renewal.</h2><p>Build the plan. Agree the terms. Follow the money.<br className="home-desktop-break" />One workspace keeps the whole cycle in view.</p></div><div className="home-product-layout"><div className="home-product-story"><div role="tablist" aria-label="Explore the subscription workflow" className="home-tabs">{stages.map((item,index)=><button key={item.id} ref={element=>{tabs.current[index]=element}} id={`home-tab-${item.id}`} type="button" role="tab" aria-selected={stage===item.id} aria-controls="home-stage-panel" tabIndex={stage===item.id?0:-1} onKeyDown={event=>tabKey(event,index)} onClick={()=>setStage(item.id)}>{item.label}</button>)}</div><div className="home-stage-copy"><span className="home-stage-number">{current.number}<span> / 04</span></span><h3>{current.title}</h3><p>{current.description}</p><a href="/app" className="home-dark-link">See it in the workspace<ArrowRight size={17} aria-hidden="true" /></a></div><p className="home-preview-disclaimer">Product previews use illustrative records.<br />Your workspace uses your saved data.</p></div><div id="home-stage-panel" role="tabpanel" aria-labelledby={`home-tab-${stage}`} className="home-product-stage" tabIndex={0}><StagePreview stage={stage} /></div></div><div className="home-principles"><div><span><Layers3 size={20} aria-hidden="true" /></span><h3>One connected record.</h3><p>Products, subscriptions, invoices and payments share the same story.</p></div><div><span><ShieldCheck size={20} aria-hidden="true" /></span><h3>Clarity at every step.</h3><p>Roles and ownership keep customer records in the right hands.</p></div><div><span><RefreshCw size={20} aria-hidden="true" /></span><h3>Built around the cycle.</h3><p>Recurring schedules and linked renewals keep the next step visible.</p></div></div></section>
    <section className="home-cycleguard home-section" id="cycleguard" aria-labelledby="home-cycle-title"><div className="home-cycle-copy"><p className="home-section-kicker">CYCLEGUARD</p><h2 id="home-cycle-title">Know what needs<br />your attention.</h2><p>Keep billing health in view. CycleGuard brings record-linked signals into the workspace, so the next action starts with context.</p><a href="/app" className="home-text-link">Explore your workspace<ArrowRight size={18} aria-hidden="true" /></a><span className="home-cycle-footnote">Explainable records. No black-box forecasts.</span></div><div className="home-cycle-visual"><img src="/assets/home/cycle.webp" srcSet="/assets/home/cycle-small.webp 960w, /assets/home/cycle.webp 1672w" sizes="(max-width: 800px) 100vw, 50vw" alt="" loading="lazy" /><div className="home-health-panel"><div className="home-health-heading"><span className="home-health-symbol"><ShieldCheck size={20} aria-hidden="true" /></span><div><strong>CycleGuard</strong><span>Billing health, with context</span></div><span className="home-health-preview">PREVIEW</span></div><div className="home-health-row"><span className="home-health-indicator" /><div><strong>Overdue balances</strong><span>Trace the amount to its invoice.</span></div><ArrowRight size={17} aria-hidden="true" /></div><div className="home-health-row"><span className="home-health-indicator muted" /><div><strong>Billing periods</strong><span>Review the outcome for each cycle.</span></div><ArrowRight size={17} aria-hidden="true" /></div><div className="home-health-row"><span className="home-health-indicator muted" /><div><strong>Email status</strong><span>Separate queued from accepted.</span></div><ArrowRight size={17} aria-hidden="true" /></div><div className="home-health-caption">Illustrative signals · open the app for actual records</div></div></div></section>
    <section className="home-team home-section" id="team" aria-labelledby="home-team-title"><div className="home-team-heading"><div><p className="home-section-kicker">THE PEOPLE BEHIND CADENTRA</p><h2 id="home-team-title">Built for the people<br />behind every cycle.</h2></div><p>A small team building a clearer way to manage the subscription cycle—from the foundations to the final detail.</p></div><div className="home-people">{people.map(person=><article key={person.name}><h3>{person.name}</h3><p className="home-person-role">{person.role}</p><p>{person.description}</p></article>)}</div></section>
    <section className="home-final-cta"><h2>Bring every<br />cycle together.</h2><a className="home-button" href="/app">Open app<ArrowRight size={19} aria-hidden="true" /></a></section>
    <footer className="home-footer"><a href="#" className="home-wordmark">Cadentra<span>.</span></a><p>Every subscription. Every cycle. Accounted for.</p><div><a href="#product">Product</a><a href="#team">Our team</a><a href="/PROJECT_STATUS.html">Project status</a><a href="https://github.com/9MidhunPM/Cadentra" target="_blank" rel="noopener noreferrer">GitHub</a><a href="/app">Open app<ArrowRight size={14} aria-hidden="true" /></a></div><span>Built for the Subscription Management System challenge.</span></footer>
  </main>
}

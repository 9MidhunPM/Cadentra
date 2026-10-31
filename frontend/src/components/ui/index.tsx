import { cloneElement, createContext, useContext, useRef, useState, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { getErrorMessage } from '../../lib/api';
import './ui.css';

export function Button({ variant = 'primary', pending = false, disabled, className = '', children, type = 'button', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger'; pending?: boolean }) {
  return <button {...props} type={type} className={`ui-button ui-button--${variant} ${className}`} disabled={disabled || pending} aria-busy={pending || undefined}>{pending && <span className="ui-spinner" aria-hidden="true" />}{children}</button>;
}

export function PageHeader({ title, description, eyebrow, actions }: { title: string; description?: string; eyebrow?: string; actions?: ReactNode }) {
  return <header className="ui-page-header"><div>{eyebrow && <p className="ui-eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="ui-muted">{description}</p>}</div>{actions && <div className="ui-actions">{actions}</div>}</header>;
}

export type TableColumn<T> = { key: string; header: string; render: (row: T) => ReactNode };
export function DataTable<T>({ columns, rows, getRowKey, page, pageSize, total, onPageChange, emptyTitle = 'No records found', caption = 'Records' }: { columns: TableColumn<T>[]; rows: T[]; getRowKey: (row: T) => string; page: number; pageSize: number; total: number; onPageChange: (page: number) => void; emptyTitle?: string; caption?: string }) {
  const pages = Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
  return <div className="ui-table-panel"><div className="ui-table-scroll" role="region" aria-label={caption} tabIndex={0}><table className="ui-table"><caption className="ui-sr-only">{caption}</caption><thead><tr>{columns.map(column => <th key={column.key} scope="col">{column.header}</th>)}</tr></thead><tbody>{rows.length ? rows.map(row => <tr key={getRowKey(row)}>{columns.map(column => <td key={column.key}>{column.render(row)}</td>)}</tr>) : <tr><td colSpan={Math.max(1, columns.length)}><EmptyState title={emptyTitle} /></td></tr>}</tbody></table></div><nav className="ui-pagination" aria-label={`${caption} pagination`}><span className="ui-muted">{total} {total === 1 ? 'record' : 'records'} · Page {page} of {pages}</span><div className="ui-actions"><Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</Button><Button variant="secondary" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Next</Button></div></nav></div>;
}

/** Format the canonical decimal string without converting any money to Number. */
export function Money({ amount, currency = 'INR' }: { amount: string; currency?: string }) {
  if (!/^-?\d+(?:\.\d{1,2})?$/.test(amount)) return <span className="ui-money" aria-label="Amount unavailable">—</span>;
  const negative = amount.startsWith('-');
  const [whole, fraction = ''] = amount.replace(/^-/, '').split('.');
  const grouped = new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US').format(BigInt(whole));
  return <span className="ui-money">{currency} {negative ? '−' : ''}{grouped}.{fraction.padEnd(2, '0')}</span>;
}

export function DateLabel({ value }: { value: string }) {
  const date = new Date(`${value}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) return <span aria-label="Date unavailable">—</span>;
  return <time dateTime={value}>{new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date)}</time>;
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const tone = ['ACTIVE', 'PAID', 'CONFIRMED'].includes(normalized) ? 'success' : ['OVERDUE', 'FAILED', 'CANCELLED'].includes(normalized) ? 'danger' : ['PAUSED', 'QUOTATION', 'PARTIALLY_PAID'].includes(normalized) ? 'warning' : 'neutral';
  return <span className={`ui-badge ui-badge--${tone}`}><span aria-hidden="true" className="ui-badge-dot" />{status.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase())}</span>;
}

type ControlProps = { id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean | 'true' | 'false' | 'grammar' | 'spelling' };
export function FormField({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: string; children: ReactElement<ControlProps> }) {
  const describedBy = [children.props['aria-describedby'], hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ');
  return <div className="ui-field"><label htmlFor={id}>{label}</label>{cloneElement(children, { id, 'aria-describedby': describedBy || undefined, 'aria-invalid': error ? true : children.props['aria-invalid'] })}{hint && <p id={`${id}-hint`} className="ui-field-hint">{hint}</p>}{error && <p id={`${id}-error`} className="ui-field-error" role="alert">{error}</p>}</div>;
}

export function ConfirmDialog({ trigger, title, description, confirmLabel = 'Confirm', onConfirm }: { trigger?: ReactElement; title: string; description: string; confirmLabel?: string; onConfirm: () => void | Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  async function confirm() {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    try { await onConfirm(); setOpen(false); }
    catch (error) { setError(getErrorMessage(error)); }
    finally { inFlight.current = false; setPending(false); }
  }
  return <Dialog.Root open={open} onOpenChange={next => { if (!inFlight.current) { setOpen(next); setError(null); } }}><Dialog.Trigger asChild>{trigger ?? <Button variant="secondary">Continue</Button>}</Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="ui-dialog-overlay" /><Dialog.Content className="ui-dialog" onOpenAutoFocus={event => { event.preventDefault(); cancelRef.current?.focus(); }} onEscapeKeyDown={event => { if (pending) event.preventDefault(); }} onPointerDownOutside={event => { if (pending) event.preventDefault(); }}><Dialog.Title>{title}</Dialog.Title><Dialog.Description className="ui-muted">{description}</Dialog.Description>{error && <ErrorPanel message={error} />}<div className="ui-dialog-actions"><Dialog.Close asChild><button className="ui-button ui-button--secondary" type="button" disabled={pending} ref={cancelRef}>Cancel</button></Dialog.Close><Button pending={pending} onClick={() => void confirm()}>{confirmLabel}</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return <div className="ui-empty"><span className="ui-empty-mark" aria-hidden="true">—</span><h2>{title}</h2>{description && <p className="ui-muted">{description}</p>}</div>;
}
export function ErrorPanel({ title = 'Something went wrong', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return <div className="ui-error" role="alert"><strong>{title}</strong><p>{message}</p>{onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}</div>;
}
export function LoadingSkeleton({ label = 'Loading' }: { label?: string }) {
  return <div className="ui-loading" role="status" aria-label={label}><span className="ui-sr-only">{label}</span><div /><div /><div /></div>;
}
const lifecycle = ['DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'CLOSED'];
export function SubscriptionStepper({ state }: { state: string }) {
  const current = lifecycle.indexOf(state.toUpperCase());
  return <ol className="ui-stepper" aria-label="Subscription lifecycle">{lifecycle.map((step, index) => <li key={step} className={index <= current ? 'ui-step-complete' : undefined} aria-current={index === current ? 'step' : undefined}><span className="ui-step-number" aria-hidden="true">{index + 1}</span><span>{step.toLowerCase().replace(/^./, c => c.toUpperCase())}</span></li>)}</ol>;
}

type ToastTone = 'success' | 'error' | 'info';
type ToastContextValue = { toast: (message: string, tone?: ToastTone) => void };
const ToastContext = createContext<ToastContextValue | null>(null);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<{ id: number; message: string; tone: ToastTone }[]>([]);
  const nextId = useRef(0);
  function toast(message: string, tone: ToastTone = 'info') { setMessages(current => [...current, { id: ++nextId.current, message, tone }].slice(-4)); }
  return <ToastContext.Provider value={{ toast }}>{children}<div className="ui-toasts" aria-label="Notifications">{messages.map(item => <div className={`ui-toast ui-toast--${item.tone}`} key={item.id}><span role={item.tone === 'error' ? 'alert' : 'status'}>{item.message}</span><button type="button" onClick={() => setMessages(current => current.filter(message => message.id !== item.id))} aria-label="Dismiss notification">×</button></div>)}</div></ToastContext.Provider>;
}
export function useToast() { const context = useContext(ToastContext); if (!context) throw new Error('useToast requires ToastProvider'); return context; }

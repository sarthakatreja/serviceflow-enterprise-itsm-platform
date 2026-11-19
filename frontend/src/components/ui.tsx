import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { AlertCircle, ArrowDown, CheckCircle2, ChevronLeft, ChevronRight, Inbox, LoaderCircle, Search, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Load } from '../api'
import { assetStatuses, priorities, slaStates, statuses, type Page, type Priority, type SlaState, type Status } from '../types'

export function PageHeading({ title, description, children }: { title: string; description?: string; children?: ReactNode }) {
  return <div className="page-heading">
    <div><h1>{title}</h1>{description && <p>{description}</p>}</div>
    {children && <div className="heading-actions">{children}</div>}
  </div>
}

export function Panel({ title, caption, action, children, className = '' }: {
  title?: string; caption?: string; action?: ReactNode; children: ReactNode; className?: string
}) {
  return <section className={'panel ' + className}>
    {title && <div className="panel-heading">
      <div><h2>{title}</h2>{caption && <p>{caption}</p>}</div>{action}
    </div>}
    {children}
  </section>
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="field">
    <span className="field-label">{label}</span>
    {children}
    {hint && <small>{hint}</small>}
  </label>
}

export function Options({ labels, only }: { labels: Record<string, string>; only?: string[] }) {
  return <>{(only ?? Object.keys(labels)).map(value => <option key={value} value={value}>{labels[value]}</option>)}</>
}

export function FilterSelect({ label, value, onChange, options, all }: {
  label: string; value: string; onChange: (value: string) => void; options: Record<string, string>; all?: string
}) {
  return <Field label={label}><select value={value} onChange={event => onChange(event.target.value)}>
    {all && <option value="">{all}</option>}<Options labels={options} />
  </select></Field>
}

export function SearchBox({ defaultValue, placeholder, onSearch }: {
  defaultValue: string; placeholder: string; onSearch: (value: string) => void
}) {
  const [term, setTerm] = useState(defaultValue)
  const submit = (event: FormEvent) => { event.preventDefault(); onSearch(term.trim()) }
  return <form className="search-field" role="search" onSubmit={submit}>
    <label>
      <Search size={17} aria-hidden="true" />
      <input aria-label={placeholder} placeholder={placeholder} type="search" maxLength={120}
        value={term} onChange={event => setTerm(event.target.value)} />
    </label>
    <button type="submit" className="button button-quiet">Search</button>
  </form>
}

export function Badge({ value, children }: { value: string; children: ReactNode }) {
  return <span className={'badge badge-' + value}><i aria-hidden="true" />{children}</span>
}

export function StatusBadge({ status }: { status: Status }) { return <Badge value={status}>{statuses[status]}</Badge> }
export function PriorityBadge({ priority }: { priority: Priority }) { return <Badge value={priority}>{priorities[priority]}</Badge> }
export function SlaBadge({ state }: { state: SlaState }) { return <Badge value={state}>{slaStates[state]}</Badge> }
export function AssetBadge({ status }: { status: keyof typeof assetStatuses }) {
  return <Badge value={status}>{assetStatuses[status]}</Badge>
}

export function Avatar({ name, size = 'sm' }: { name: string; size?: 'sm' | 'md' | 'lg' }) {
  const words = name.trim().split(/\s+/)
  const initials = (words[0][0] + (words.length > 1 ? words[words.length - 1][0] : '')).toUpperCase()
  const tint = [...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 5
  return <span className={'avatar avatar-' + size + ' avatar-tint-' + tint} aria-hidden="true">{initials}</span>
}

const timestamp = new Intl.DateTimeFormat('en-AU', {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hourCycle: 'h23',
})
const dayFormat = new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', timeZone: 'UTC' })
export const formatTimestamp = (iso: string) => timestamp.format(new Date(iso))
const fullDate = new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
export const formatDay = (iso: string, includeYear = false) => (includeYear ? fullDate : dayFormat).format(new Date(iso))

export function TimeLeft({ seconds }: { seconds: number | null }) {
  if (seconds === null) return <span className="muted">Completed</span>
  const hours = Math.floor(Math.abs(seconds) / 3600)
  const minutes = Math.floor(Math.abs(seconds) % 3600 / 60)
  const duration = hours > 0 ? hours + 'h ' + minutes + 'm' : minutes + 'm'
  return <span className="muted tabular">{duration + (seconds < 0 ? ' overdue' : ' left')}</span>
}

export function Notice({ error, success }: { error?: string; success?: string }) {
  if (error) return <div className="notice notice-error" role="alert"><AlertCircle size={18} />{error}</div>
  if (success) return <div className="notice notice-success" role="status"><CheckCircle2 size={18} />{success}</div>
  return null
}

export function Empty({ title, description }: { title: string; description?: string }) {
  return <div className="empty"><span className="empty-icon"><Inbox size={20} /></span>
    <strong>{title}</strong>{description && <p>{description}</p>}
  </div>
}

export function Loading({ label = 'Loading workspace…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle size={19} className="spin" />{label}</div>
}

export function RequestState({ load }: { load: Pick<Load<unknown>, 'error' | 'pending' | 'reload'> }) {
  if (load.error) return <div className="fetch-error">
    <Notice error={load.error} />
    <button type="button" className="button button-quiet" onClick={load.reload}>Retry</button>
  </div>
  return <Loading />
}

export function Pagination<T>({ page, onOffset, label }: {
  page: Page<T>; onOffset: (offset: number) => void; label: string
}) {
  const count = page.items.length
  const right = page.offset + count
  return <div className="pagination">
    <span>{count > 0 ? (page.offset + 1) + '–' + right + ' of ' + page.total : page.total} {label}</span>
    <div className="pagination-controls">
      <button type="button" className="icon-button" aria-label="Previous page" disabled={page.offset === 0}
        onClick={() => onOffset(Math.max(0, page.offset - page.limit))}><ChevronLeft size={18} /></button>
      <button type="button" className="icon-button" aria-label="Next page" disabled={right >= page.total || count === 0}
        onClick={() => onOffset(page.offset + page.limit)}><ChevronRight size={18} /></button>
    </div>
  </div>
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link className="back-link" to={to}><ChevronLeft size={16} />{children}</Link>
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => element?.close()
  }, [])
  return <dialog className="modal" ref={dialog} aria-labelledby="modal-title"
    onCancel={event => { event.preventDefault(); onClose() }}>
    <div className="modal-heading"><h2 id="modal-title">{title}</h2>
      <button className="icon-button" type="button" onClick={onClose} aria-label="Close dialog"><X size={19} /></button>
    </div>
    <div className="modal-body">{children}</div>
  </dialog>
}

export function RankedBars({ rows, label, tone = 'teal' }: {
  rows: { label: string; value: number; link?: string }[]; label: string; tone?: 'teal' | 'blue'
}) {
  const max = Math.max(1, ...rows.map(row => row.value))
  return <ul className={'ranked-bars tone-' + tone} aria-label={label}>
    {rows.map(row => <li key={row.label}>
      <div className="rank-label">
        {row.link ? <Link to={row.link}>{row.label}</Link> : <span>{row.label}</span>}
        <strong className="tabular">{row.value}</strong>
      </div>
      <div className="rank-track" aria-hidden="true"><span style={{ width: row.value * 100 / max + '%' }} /></div>
    </li>)}
  </ul>
}

export function DownloadButton({ busy, disabled, onClick }: { busy: boolean; disabled?: boolean; onClick: () => void }) {
  return <button type="button" className="button button-primary" disabled={busy || disabled} onClick={onClick}>
    <ArrowDown size={17} />{busy ? 'Preparing export…' : 'Export CSV'}
  </button>
}

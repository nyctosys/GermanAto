import type { FormEvent, ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function PageHeader({
  title,
  actions,
}: {
  title: string
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error || 'Request failed')
  return <div className="error-box">{msg}</div>
}

export function SuccessBox({ children }: { children: ReactNode }) {
  return <div className="success-box">{children}</div>
}

export function Loading() {
  return <p className="muted">Loading…</p>
}

export function Empty({ children = 'No records found' }: { children?: ReactNode }) {
  return <p className="muted empty">{children}</p>
}

export function Money({ value }: { value: number | string | null | undefined }) {
  const n = Number(value || 0)
  return (
    <span className="num">
      {n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PKR
    </span>
  )
}

export function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  )
}

export function FormGrid({
  children,
  onSubmit,
}: {
  children: ReactNode
  onSubmit?: (e: FormEvent) => void
}) {
  if (onSubmit) {
    return (
      <form className="form-grid" onSubmit={onSubmit}>
        {children}
      </form>
    )
  }
  return <div className="form-grid">{children}</div>
}

export function Panel({
  title,
  children,
  actions,
}: {
  title?: string
  children: ReactNode
  actions?: ReactNode
}) {
  return (
    <section className="panel">
      {(title || actions) && (
        <div className="panel-head">
          {title ? <h2>{title}</h2> : <span />}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function StatusBadge({
  status,
  tone,
}: {
  status: string
  tone?: 'ok' | 'warn' | 'danger' | 'info'
}) {
  const cls = tone ? `status-badge is-${tone}` : 'status-badge'
  return <span className={cls}>{status.replaceAll('_', ' ')}</span>
}

export function PillStat({
  value,
  label,
  sub,
  dark,
  to,
}: {
  value: number | string
  label: string
  sub?: string
  dark?: boolean
  to?: string
}) {
  const inner = (
    <>
      <div className="pill-num">{value}</div>
      <div>
        {label}
        {sub ? <div className={`pill-sub${dark ? '' : ' accent'}`}>{sub}</div> : null}
      </div>
    </>
  )
  const cls = `pill-stat ${dark ? 'is-dark' : 'is-light'}`
  if (to) return <Link className={cls} to={to}>{inner}</Link>
  return <div className={cls}>{inner}</div>
}

export function KpiCard({
  label,
  value,
  trend,
  to,
  variant = 'light',
  span = 3,
  children,
  progress,
}: {
  label: string
  value?: number | string
  trend?: string
  to?: string
  variant?: 'light' | 'dark' | 'orange' | 'muted'
  span?: 3 | 4 | 5 | 6 | 8 | 12
  children?: ReactNode
  progress?: number
}) {
  const v =
    variant === 'dark' ? 'is-dark' : variant === 'orange' ? 'is-orange' : variant === 'muted' ? 'is-muted' : ''
  return (
    <div className={`kpi-card span-${span} ${v}`.trim()}>
      {to ? (
        <Link className="kpi-link" to={to} aria-label="Open details">
          ↗
        </Link>
      ) : null}
      <div className="kpi-label">{label}</div>
      {value !== undefined ? <div className="kpi-value">{value}</div> : null}
      {trend ? <div className="kpi-trend">{trend}</div> : null}
      {children}
      {progress !== undefined ? (
        <div className="progress-thin">
          <i style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} />
        </div>
      ) : null}
    </div>
  )
}

export function DotGrid({ total = 16, on = 0 }: { total?: number; on?: number }) {
  return (
    <div className="dot-grid" aria-hidden>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i < on ? 'on' : ''} />
      ))}
    </div>
  )
}

export function Dialog({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
}) {
  if (!open) return null
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  )
}

export function NextActionBanner({
  label,
  href,
  hrefLabel,
}: {
  label: string
  href?: string
  hrefLabel?: string
}) {
  return (
    <div className="next-action">
      <strong>Next:</strong> {label}
      {href ? (
        <>
          {' '}
          <Link className="btn btn-sm" to={href}>
            {hrefLabel || 'Continue'}
          </Link>
        </>
      ) : null}
    </div>
  )
}

export function DataTable({
  columns,
  rows,
  empty = 'No records found',
}: {
  columns: { key: string; label: string }[]
  rows: Record<string, ReactNode>[]
  empty?: string
}) {
  if (!rows.length) return <Empty>{empty}</Empty>
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key}>{row[c.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

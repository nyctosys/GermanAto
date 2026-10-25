import type { FormEvent, ReactNode } from 'react'

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

export function Loading() {
  return <p className="muted">Loading…</p>
}

export function Empty({ children = 'No records found' }: { children?: ReactNode }) {
  return <p className="muted empty">{children}</p>
}

export function Money({ value }: { value: number | string | null | undefined }) {
  const n = Number(value || 0)
  return <span>{n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PKR</span>
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
  // Always a div so pages can wrap a single outer <form> without nesting.
  // When onSubmit is provided, wrap with a form for standalone submit flows.
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

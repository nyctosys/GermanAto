import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Money } from './ui'

export type JobStep = 'work' | 'check' | 'handover'

const STEPS: { id: JobStep; n: number; title: string; path: (id: string) => string }[] = [
  {
    id: 'work',
    n: 1,
    title: 'Do the work',
    path: (id) => `/repair-orders/${id}/execution`,
  },
  {
    id: 'check',
    n: 2,
    title: 'Check quality',
    path: (id) => `/repair-orders/${id}/pipeline`,
  },
  {
    id: 'handover',
    n: 3,
    title: 'Hand over car',
    path: (id) => `/repair-orders/${id}/pipeline#handover`,
  },
]

export function friendlyStatus(status?: string | null): string {
  const s = (status || '').toLowerCase()
  if (s === 'received') return 'Waiting to start'
  if (s === 'in_progress') return 'Work in progress'
  if (s === 'waiting_parts') return 'Waiting for parts'
  if (s === 'awaiting_qc') return 'Ready for check'
  if (s === 'completed' || s === 'complete') return 'Work finished'
  if (s === 'delivered') return 'Car delivered'
  if (s === 'cancelled' || s === 'canceled') return 'Cancelled'
  return status || '—'
}

export function friendlyDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value.includes('T') ? value : value.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusPillClass(status?: string | null): string {
  const s = (status || '').toLowerCase()
  if (s === 'in_progress') return 'is-progress'
  if (s === 'waiting_parts' || s === 'received') return 'is-waiting'
  if (s === 'awaiting_qc' || s === 'completed' || s === 'complete') return 'is-ready'
  if (s === 'delivered') return 'is-done'
  if (s === 'cancelled' || s === 'canceled') return 'is-danger'
  return ''
}

/** Back link + 3-step tabs for every RO screen. */
export function RepairJobFlow({
  roId,
  step,
  vehicleLabel,
}: {
  roId: string | number
  step: JobStep
  vehicleLabel?: string
}) {
  const id = String(roId)
  const activeIdx = STEPS.findIndex((x) => x.id === step)

  return (
    <div className="job-flow">
      <div className="job-flow-top">
        <Link className="job-flow-back" to="/repair-orders">
          ← All repair orders
        </Link>
        {vehicleLabel ? <span className="job-flow-vehicle">{vehicleLabel}</span> : null}
      </div>

      <nav className="job-tabs" aria-label="Job steps" role="tablist">
        {STEPS.map((s, i) => {
          const active = s.id === step
          const done = activeIdx > i
          return (
            <Link
              key={s.id}
              to={s.path(id)}
              role="tab"
              aria-selected={active}
              className={`job-tab${active ? ' is-active' : ''}${done ? ' is-done' : ''}`}
            >
              <span className="job-tab-n" aria-hidden>
                {done && !active ? '✓' : s.n}
              </span>
              <span className="job-tab-label">{s.title}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}

export type JobSummaryProps = {
  jobId: string | number
  vehicle?: string | null
  regNo?: string | null
  customerName?: string | null
  customerPhone?: string | null
  mileage?: string | null
  vin?: string | null
  color?: string | null
  status?: string | null
  technician?: string | null
  dueAt?: string | null
  labourDone?: number
  labourTotal?: number
  labourCost?: number
  partsCost?: number
  jobCost?: number
  complaint?: string | null
  plan?: string | null
  actions?: ReactNode
}

/** Compact vehicle / schedule / cost strip for RO screens. */
export function JobSummary({
  jobId,
  vehicle,
  regNo,
  customerName,
  customerPhone,
  mileage,
  vin,
  color,
  status,
  technician,
  dueAt,
  labourDone,
  labourTotal,
  labourCost = 0,
  partsCost = 0,
  jobCost = 0,
  complaint,
  plan,
  actions,
}: JobSummaryProps) {
  const title = [vehicle, regNo].filter(Boolean).join(' · ') || `Job #${jobId}`
  const pct =
    labourTotal && labourTotal > 0
      ? Math.min(100, Math.round(((labourDone || 0) / labourTotal) * 100))
      : 0

  return (
    <section className="job-summary">
      <div className="job-summary-head">
        <div className="job-summary-title">
          <p className="job-summary-eyebrow">Job #{jobId}</p>
          <h1>{title}</h1>
          <p className="job-summary-sub muted">
            {[customerName, customerPhone].filter(Boolean).join(' · ') || '—'}
          </p>
        </div>
        <div className="job-summary-head-aside">
          <span className={`status-pill ${statusPillClass(status)}`}>
            {friendlyStatus(status)}
          </span>
          {actions}
        </div>
      </div>

      <div className="job-summary-grid">
        <div className="job-summary-card">
          <h3>Vehicle</h3>
          <dl className="job-meta">
            <div>
              <dt>Mileage</dt>
              <dd>{mileage || '—'}</dd>
            </div>
            <div>
              <dt>VIN</dt>
              <dd className="num">{vin || '—'}</dd>
            </div>
            <div>
              <dt>Color</dt>
              <dd>{color || '—'}</dd>
            </div>
          </dl>
        </div>

        <div className="job-summary-card">
          <h3>Schedule</h3>
          <dl className="job-meta">
            <div>
              <dt>Technician</dt>
              <dd>{technician || '—'}</dd>
            </div>
            <div>
              <dt>Due</dt>
              <dd>{friendlyDate(dueAt)}</dd>
            </div>
            <div>
              <dt>Tasks</dt>
              <dd>
                {labourTotal != null
                  ? `${labourDone ?? 0} / ${labourTotal}`
                  : '—'}
              </dd>
            </div>
          </dl>
          {labourTotal != null && labourTotal > 0 ? (
            <div
              className="job-progress"
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Task progress"
            >
              <span style={{ width: `${pct}%` }} />
            </div>
          ) : null}
        </div>

        <div className="job-summary-card job-summary-costs">
          <h3>Job cost</h3>
          <dl className="job-meta">
            <div>
              <dt>Labour</dt>
              <dd>
                <Money value={labourCost} />
              </dd>
            </div>
            <div>
              <dt>Parts</dt>
              <dd>
                <Money value={partsCost} />
              </dd>
            </div>
            <div className="job-meta-total">
              <dt>Total</dt>
              <dd>
                <Money value={jobCost} />
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {(complaint || plan) && (
        <div className="job-summary-notes">
          {complaint ? (
            <div>
              <span className="job-note-label">Complaint</span>
              <p>{complaint}</p>
            </div>
          ) : null}
          {plan ? (
            <div>
              <span className="job-note-label">Plan</span>
              <p>{plan}</p>
            </div>
          ) : null}
        </div>
      )}
    </section>
  )
}

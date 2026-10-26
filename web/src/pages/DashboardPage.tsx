import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import {
  DotGrid,
  Empty,
  ErrorBox,
  KpiCard,
  Loading,
  Money,
  PageHeader,
  Panel,
  PillStat,
} from '../components/ui'

type Kpis = {
  open_jobs: number
  overdue_jobs: number
  open_jobs_delta_pct: number
  unassigned: number
  unassigned_pct_of_open: number
  pending_approvals: number
  in_repair: number
  qc_waiting: number
  receivables: number
  unpaid_invoices: number
  low_stock: number
  low_stock_items?: { id: number; name: string; quantity: number }[]
  revenue_month: number
  workload?: { name: string; count: number }[]
  open_job_cards: number
  delivered_today: number
}

type DashboardData = {
  kpis?: Kpis
  sections: Record<string, unknown>
  unavailable?: string[]
  role?: string
}

export function DashboardPage() {
  const { user } = useAuth()
  const q = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardData>('/api/dashboard'),
  })

  if (q.isLoading) return <Loading />
  if (q.error) return <ErrorBox error={q.error} />

  const k = q.data?.kpis
  if (!k) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <Empty>No KPI data available</Empty>
      </div>
    )
  }

  const maxWorkload = Math.max(1, ...(k.workload || []).map((w) => w.count))

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.username || ''}`} />
      <div className="bento">
        <div className="span-3 stack" style={{ gap: 14 }}>
          <PillStat
            value={k.open_jobs}
            label="all open jobs"
            sub={`${k.overdue_jobs} overdue`}
            to="/repair-orders"
          />
          <PillStat
            value={k.unassigned}
            label="unassigned jobs"
            sub={`${k.unassigned_pct_of_open}% of open`}
            dark
            to="/repair-orders"
          />
        </div>

        <KpiCard
          span={4}
          variant="muted"
          label="Incoming job load"
          value={k.open_job_cards}
          trend={`${k.open_jobs_delta_pct >= 0 ? '+' : ''}${k.open_jobs_delta_pct}% vs prior open baseline`}
          to="/job-cards"
          progress={Math.min(100, k.open_job_cards * 5)}
        />

        <KpiCard
          span={5}
          variant="muted"
          label="Pending approvals"
          value={k.pending_approvals}
          trend="Quotes awaiting customer line decisions"
          to="/quotes/pending"
        >
          <DotGrid total={16} on={Math.min(16, k.pending_approvals)} />
        </KpiCard>

        <KpiCard
          span={4}
          label="Open by customer / status"
          value={k.in_repair}
          trend="Jobs in workshop"
          to="/repair-orders"
        >
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 64, marginTop: 8 }}>
            {(k.workload || []).slice(0, 8).map((w) => (
              <div key={w.name} title={`${w.name}: ${w.count}`} style={{ flex: 1, textAlign: 'center' }}>
                <div
                  style={{
                    height: `${(w.count / maxWorkload) * 56}px`,
                    background: w.name === 'Unassigned' ? 'var(--orange)' : 'var(--black)',
                    borderRadius: 4,
                  }}
                />
                <div style={{ fontSize: 9, marginTop: 4 }} className="muted">
                  {w.name.slice(0, 3)}
                </div>
              </div>
            ))}
          </div>
        </KpiCard>

        <KpiCard span={4} variant="orange" label="GermanATO">
          <p style={{ fontSize: '1.15rem', fontWeight: 600, lineHeight: 1.35, marginTop: 8 }}>
            It will change the way you manage your workshop
          </p>
          <div style={{ marginTop: 'auto', fontSize: '3rem', opacity: 0.9 }}>⚡</div>
          <p style={{ fontSize: '0.8rem', opacity: 0.85 }}>just start using / ERP</p>
        </KpiCard>

        <KpiCard
          span={4}
          variant="muted"
          label="QC waiting"
          value={k.qc_waiting}
          trend="Largest share needs foreman sign-off"
          to="/repair-orders"
        >
          <svg width="120" height="120" viewBox="0 0 120 120" style={{ margin: '8px auto' }}>
            <circle cx="60" cy="60" r="48" fill="none" stroke="#ddd" strokeWidth="10" />
            <circle
              cx="60"
              cy="60"
              r="48"
              fill="none"
              stroke="var(--orange)"
              strokeWidth="10"
              strokeDasharray={`${Math.min(300, k.qc_waiting * 20)} 300`}
              transform="rotate(-90 60 60)"
            />
            <text x="60" y="66" textAnchor="middle" className="num" fontSize="28" fontWeight="700">
              {k.qc_waiting}
            </text>
          </svg>
        </KpiCard>

        <KpiCard
          span={3}
          label="High priority / overdue"
          value={k.overdue_jobs}
          trend="Open &gt; 7 days without update"
          to="/repair-orders"
        />

        <KpiCard
          span={3}
          label="Receivables"
          value={undefined}
          to="/invoices"
        >
          <div className="kpi-value" style={{ fontSize: '1.6rem' }}>
            <Money value={k.receivables} />
          </div>
          <div className="kpi-trend">{k.unpaid_invoices} unpaid invoices</div>
        </KpiCard>

        <KpiCard
          span={3}
          label="Revenue (month)"
          value={undefined}
          to="/reports"
        >
          <div className="kpi-value" style={{ fontSize: '1.6rem' }}>
            <Money value={k.revenue_month} />
          </div>
          <div className="kpi-trend">Paid + advances applied this month</div>
        </KpiCard>

        <KpiCard
          span={3}
          label="Low stock"
          value={k.low_stock}
          trend="At or below reorder level"
          to="/inventory"
        />

        <KpiCard span={6} variant="dark" label="Create your custom view">
          <p style={{ marginTop: 8 }}>/ open job cards or quotes to continue the workflow</p>
          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <Link className="btn" to="/job-cards/new">
              + Job card
            </Link>
            <Link className="btn btn-secondary" to="/quotes/pending">
              Quotes
            </Link>
          </div>
        </KpiCard>

        <KpiCard span={6} label="Delivered today" value={k.delivered_today} to="/repair-orders" />
      </div>

      {(k.low_stock_items || []).length > 0 ? (
        <Panel title="Low stock alerts">
          <ul>
            {k.low_stock_items!.map((i) => (
              <li key={i.id}>
                <Link to="/inventory">
                  {i.name} — qty {i.quantity}
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      {q.data?.unavailable?.length ? (
        <p className="muted">Some sections unavailable: {q.data.unavailable.join(', ')}</p>
      ) : null}
    </div>
  )
}

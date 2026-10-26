import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

type Kpi = {
  label: string
  value: number
  href: string
  meta?: string | null
  alert?: boolean
  kind?: 'money' | 'number'
}

type ChartPoint = { date: string; total: number }

type Alert = {
  level: string
  code: string
  message: string
  href: string
}

type DashboardData = {
  role?: string
  view?: string
  date_range?: { start?: string; end?: string; period?: string }
  kpis?: Kpi[]
  charts?: {
    revenue_daily?: ChartPoint[]
    cash_daily?: ChartPoint[]
    expenses_daily?: ChartPoint[]
  }
  sections?: Record<string, unknown>
  alerts?: Alert[]
  quick_actions?: Array<{ label: string; href: string }>
  unavailable?: string[]
  generated_at?: string
  error?: string
}

const VIEW_LABELS: Record<string, string> = {
  manager: 'Manager',
  accountant: 'Accountant',
  receptionist: 'Reception',
  technician: 'Technician',
  storekeeper: 'Store',
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function monthStartIso() {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10)
}

function moneyText(n: number) {
  return `${Number(n || 0).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })} PKR`
}

function daysAgo(iso?: string | null) {
  if (!iso) return ''
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

function asRows(section: unknown, keys: string[]): Record<string, unknown>[] {
  if (!section || typeof section !== 'object') return []
  const obj = section as Record<string, unknown>
  for (const key of keys) {
    if (Array.isArray(obj[key])) return obj[key] as Record<string, unknown>[]
  }
  return []
}

function MiniChart({
  title,
  series,
  color,
}: {
  title: string
  series: ChartPoint[]
  color: string
}) {
  const max = Math.max(1, ...series.map((p) => Number(p.total) || 0))
  if (!series.length) {
    return (
      <div className="dash-chart">
        <div className="dash-chart__title">{title}</div>
        <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
          No data in this range
        </p>
      </div>
    )
  }
  return (
    <div className="dash-chart">
      <div className="dash-chart__title">{title}</div>
      <div className="dash-chart__bars" role="img" aria-label={title}>
        {series.map((p) => {
          const h = Math.max(4, Math.round((Number(p.total) / max) * 72))
          return (
            <div key={p.date} className="dash-chart__col" title={`${p.date}: ${moneyText(p.total)}`}>
              <div className="dash-chart__bar" style={{ height: h, background: color }} />
              <span className="dash-chart__label">{p.date.slice(5)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SearchableList({
  title,
  href,
  rows,
  empty,
  primary,
  secondary,
  amount,
  filterPlaceholder = 'Search…',
}: {
  title: string
  href?: string
  rows: Record<string, unknown>[]
  empty: string
  primary: (row: Record<string, unknown>) => string
  secondary?: (row: Record<string, unknown>) => string
  amount?: (row: Record<string, unknown>) => ReactNode
  filterPlaceholder?: string
}) {
  const [q, setQ] = useState('')
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(needle))
  }, [rows, q])

  return (
    <Panel
      title={title}
      actions={
        href ? (
          <Link className="btn btn-secondary" to={href}>
            View all
          </Link>
        ) : null
      }
    >
      {rows.length > 3 ? (
        <input
          className="input"
          style={{ marginBottom: 10 }}
          placeholder={filterPlaceholder}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      ) : null}
      {filtered.length === 0 ? (
        <Empty>{empty}</Empty>
      ) : (
        <ul className="dash-list">
          {filtered.map((row, idx) => {
            const id = row.id ?? row.vendor_id ?? row.repair_order_id ?? idx
            const link =
              typeof row.href === 'string'
                ? (row.href as string)
                : typeof row.vendor_id === 'number'
                  ? `/vendors/${row.vendor_id}`
                  : typeof row.repair_order_id === 'number' ||
                      (typeof row.id === 'number' && /repair|vehicle|overdue|job/i.test(title))
                    ? '/repair-orders'
                    : typeof row.id === 'number' && /estimate|quote/i.test(title)
                      ? '/quotes/pending'
                      : typeof row.id === 'number' && /invoice|receivable|advance/i.test(title)
                        ? '/invoices'
                      : typeof row.id === 'number' && /payment|cash/i.test(title)
                        ? '/finance/cash-received'
                        : typeof row.id === 'number' && /expense/i.test(title)
                          ? '/finance/daily-expenses'
                          : typeof row.id === 'number' && /stock|inventory/i.test(title)
                            ? '/inventory?low_stock=1'
                            : typeof row.id === 'number' && /attend|worker/i.test(title)
                              ? '/hr/attendance'
                              : typeof row.id === 'number' && /gate/i.test(title)
                                ? '/cars?gate_pass=1'
                                : null
            const body = (
              <>
                <span className="dash-list__main">
                  <span className="dash-list__primary">{primary(row)}</span>
                  {secondary ? <span className="dash-list__secondary">{secondary(row)}</span> : null}
                </span>
                {amount ? <span className="dash-list__amount">{amount(row)}</span> : null}
              </>
            )
            return (
              <li key={String(id)}>
                {link ? (
                  <Link className="dash-list__row" to={link}>
                    {body}
                  </Link>
                ) : (
                  <div className="dash-list__row">{body}</div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const period = params.get('period') || 'month'
  const start = params.get('start_date') || monthStartIso()
  const end = params.get('end_date') || todayIso()

  const q = useQuery({
    queryKey: ['dashboard', period, start, end],
    queryFn: () => {
      const qs = new URLSearchParams({ period, start_date: start, end_date: end })
      return api.get<DashboardData>(`/api/dashboard?${qs}`)
    },
  })

  const data = q.data
  const view = data?.view || ROLE_FROM_USER(user?.role)
  const sections = data?.sections || {}

  function setPeriod(next: string) {
    const nextParams = new URLSearchParams(params)
    nextParams.set('period', next)
    if (next !== 'custom') {
      const today = todayIso()
      if (next === 'day') {
        nextParams.set('start_date', today)
        nextParams.set('end_date', today)
      } else if (next === 'week') {
        const d = new Date()
        d.setDate(d.getDate() - 6)
        nextParams.set('start_date', d.toISOString().slice(0, 10))
        nextParams.set('end_date', today)
      } else if (next === 'year') {
        nextParams.set('start_date', `${new Date().getFullYear()}-01-01`)
        nextParams.set('end_date', today)
      } else {
        nextParams.set('start_date', monthStartIso())
        nextParams.set('end_date', today)
      }
    }
    setParams(nextParams)
  }

  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="dash">
      <PageHeader
        title={`${greet}${user?.username ? `, ${user.username}` : ''}`}
        actions={
          <button type="button" className="btn btn-secondary" onClick={() => q.refetch()}>
            Refresh
          </button>
        }
      />

      <p className="muted dash-sub">
        {VIEW_LABELS[view] || 'Workshop'} view ·{' '}
        {new Date().toLocaleDateString(undefined, {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        })}
        {data?.date_range?.start
          ? ` · ${data.date_range.start} → ${data.date_range.end}`
          : null}
      </p>

      <Panel title="Date range">
        <div className="form-grid dash-filters">
          <div className="tabs" style={{ marginBottom: 0 }}>
            {(['day', 'week', 'month', 'year'] as const).map((p) => (
              <button
                key={p}
                type="button"
                className={`tab${period === p ? ' is-active' : ''}`}
                onClick={() => setPeriod(p)}
              >
                {p[0].toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
          <label className="field">
            <span>From</span>
            <input
              className="input"
              type="date"
              value={start}
              onChange={(e) => {
                const next = new URLSearchParams(params)
                next.set('period', 'custom')
                next.set('start_date', e.target.value)
                setParams(next)
              }}
            />
          </label>
          <label className="field">
            <span>To</span>
            <input
              className="input"
              type="date"
              value={end}
              onChange={(e) => {
                const next = new URLSearchParams(params)
                next.set('period', 'custom')
                next.set('end_date', e.target.value)
                setParams(next)
              }}
            />
          </label>
        </div>
      </Panel>

      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {data?.error ? <ErrorBox error={data.error} /> : null}

      {data && !data.error ? (
        <>
          {(data.alerts || []).length > 0 ? (
            <div className="dash-alerts">
              {(data.alerts || []).map((a) => (
                <Link key={a.code} to={a.href} className={`dash-alert dash-alert--${a.level}`}>
                  {a.message}
                </Link>
              ))}
            </div>
          ) : null}

          {(data.quick_actions || []).length > 0 ? (
            <Panel title="Quick actions">
              <div className="row-actions">
                {(data.quick_actions || []).map((a) => (
                  <Link key={a.href + a.label} className="btn btn-secondary" to={a.href}>
                    {a.label}
                  </Link>
                ))}
              </div>
            </Panel>
          ) : null}

          {(data.kpis || []).length > 0 ? (
            <div className="stat-grid dash-kpis">
              {(data.kpis || []).map((kpi) => (
                <Link
                  key={kpi.label}
                  to={kpi.href}
                  className={`stat dash-stat${kpi.alert ? ' dash-stat--alert' : ''}`}
                >
                  <div className="label">{kpi.label}</div>
                  <div className="value">
                    {kpi.kind === 'money' ? <Money value={kpi.value} /> : kpi.value}
                  </div>
                  {kpi.meta ? <div className="dash-stat__meta">{kpi.meta}</div> : null}
                </Link>
              ))}
            </div>
          ) : (
            <Empty>Nothing is assigned to your role yet. Use the sidebar to get started.</Empty>
          )}

          {(data.charts?.revenue_daily?.length ||
            data.charts?.cash_daily?.length ||
            data.charts?.expenses_daily?.length) ? (
            <div className="dash-charts">
              {data.charts?.revenue_daily ? (
                <MiniChart
                  title="Revenue (invoiced)"
                  series={data.charts.revenue_daily}
                  color="var(--brand)"
                />
              ) : null}
              {data.charts?.cash_daily ? (
                <MiniChart
                  title="Cash received"
                  series={data.charts.cash_daily}
                  color="#2f6f4e"
                />
              ) : null}
              {data.charts?.expenses_daily ? (
                <MiniChart
                  title="Expenses"
                  series={data.charts.expenses_daily}
                  color="#8a5a2b"
                />
              ) : null}
            </div>
          ) : null}

          <div className="dash-panels">
            {sections.payments ? (
              <SearchableList
                title="Recent payments"
                href={`/finance/cash-received?start_date=${start}&end_date=${end}`}
                rows={asRows(sections.payments, ['recent'])}
                empty="No cash receipts in this range."
                primary={(r) => String(r.description || 'Payment')}
                secondary={(r) =>
                  `${r.date || ''} · ${r.payment_method || ''}${r.invoice_id ? ` · inv #${r.invoice_id}` : ''}`
                }
                amount={(r) => <Money value={Number(r.amount || 0)} />}
              />
            ) : null}

            {sections.invoices ? (
              <SearchableList
                title="Recent invoices"
                href={`/invoices?start_date=${start}&end_date=${end}`}
                rows={asRows(sections.invoices, ['items'])}
                empty="No invoices in this range."
                primary={(r) => String(r.customer_name || 'Customer')}
                secondary={(r) =>
                  `${r.document_no || `#${r.id}`} · ${r.status || ''} · ${daysAgo(String(r.created_at || ''))}`
                }
                amount={(r) => <Money value={Number(r.net_total || 0)} />}
              />
            ) : null}

            {sections.receivables ? (
              <SearchableList
                title="Receivables (oldest first)"
                href="/invoices?status=unpaid"
                rows={asRows(sections.receivables, ['oldest', 'items'])}
                empty="Every invoice is settled."
                primary={(r) => String(r.customer_name || 'Customer')}
                secondary={(r) => `Invoice #${r.id} · raised ${daysAgo(String(r.created_at || ''))}`}
                amount={(r) => <Money value={Number(r.owed || 0)} />}
              />
            ) : null}

            {sections.customer_advances ? (
              <SearchableList
                title="Customer advances (liability)"
                href="/invoices"
                rows={asRows(sections.customer_advances, ['items'])}
                empty="No customer advances held."
                primary={(r) => String(r.customer_name || 'Customer')}
                secondary={(r) => `${r.kind || ''} · ${r.document_no || `#${r.id}`}`}
                amount={(r) => <Money value={Number(r.amount || 0)} />}
              />
            ) : null}

            {sections.quotes ? (
              <SearchableList
                title="Pending estimates"
                href="/quotes/pending"
                rows={asRows(sections.quotes, ['items'])}
                empty="No quotes are waiting."
                primary={(r) => String(r.customer_name || 'Customer')}
                secondary={(r) =>
                  `${r.quote_number || ''} · sent ${daysAgo(String(r.created_at || ''))}`
                }
                amount={(r) => <Money value={Number(r.total_amount || 0)} />}
              />
            ) : null}

            {sections.repairs ? (
              <SearchableList
                title="Active repairs"
                href="/repair-orders"
                rows={asRows(sections.repairs, ['items'])}
                empty="Nothing in the workshop right now."
                primary={(r) => String(r.customer_name || 'Customer')}
                secondary={(r) =>
                  `#${r.id} · ${r.status || ''} · ${r.customer_reg_no || ''} · ${daysAgo(String(r.created_at || ''))}`
                }
              />
            ) : null}

            {sections.repairs && asRows(sections.repairs, ['overdue']).length > 0 ? (
              <SearchableList
                title="Overdue jobs"
                href="/repair-orders?overdue=1"
                rows={asRows(sections.repairs, ['overdue'])}
                empty="No overdue jobs."
                primary={(r) => String(r.customer_name || 'Customer')}
                secondary={(r) =>
                  `#${r.id} · ${r.status || ''} · ${r.age_days ?? '?'} days open`
                }
              />
            ) : null}

            {sections.repairs ? (
              <SearchableList
                title="Vehicles in workshop"
                href="/repair-orders"
                rows={asRows(sections.repairs, ['vehicles_in_workshop'])}
                empty="No vehicles currently on open jobs."
                primary={(r) => String(r.plate || r.make || `RO #${r.repair_order_id}`)}
                secondary={(r) =>
                  `${r.customer_name || ''} · ${r.status || ''} · ${r.worker_name || 'unassigned'}`
                }
              />
            ) : null}

            {sections.expenses ? (
              <SearchableList
                title="Recent expenses"
                href={`/finance/daily-expenses?start_date=${start}&end_date=${end}`}
                rows={asRows(sections.expenses, ['recent'])}
                empty="No expenses in this range."
                primary={(r) => String(r.description || r.category || 'Expense')}
                secondary={(r) => `${r.date || ''} · ${r.category || ''}`}
                amount={(r) => <Money value={Number(r.amount || 0)} />}
              />
            ) : null}

            {sections.supplier_payables ? (
              <SearchableList
                title="Supplier payables"
                href="/vendors"
                rows={asRows(sections.supplier_payables, ['items'])}
                empty="No vendor balances owed."
                primary={(r) => String(r.vendor_name || 'Vendor')}
                amount={(r) => <Money value={Number(r.closing_balance || 0)} />}
              />
            ) : null}

            {sections.inventory ? (
              <SearchableList
                title="Low-stock alerts"
                href="/inventory?low_stock=1"
                rows={asRows(sections.inventory, ['items'])}
                empty="Stock levels are healthy."
                primary={(r) => String(r.item_name || 'Item')}
                secondary={(r) =>
                  `${r.category || ''} · reorder at ${r.reorder_level ?? '—'}${r.urgency === 'critical' ? ' · critical' : ''}`
                }
                amount={(r) => <span>{String(r.quantity ?? 0)} left</span>}
              />
            ) : null}

            {sections.hr ? (
              <SearchableList
                title="Attendance today"
                href="/hr/attendance"
                rows={[
                  ...asRows(sections.hr, ['present']).map((r) => ({ ...r, _tag: 'On site' })),
                  ...asRows(sections.hr, ['available']).map((r) => ({ ...r, _tag: 'Checked out' })),
                  ...asRows(sections.hr, ['absent']).map((r) => ({ ...r, _tag: 'Not checked in' })),
                ]}
                empty="No workers on file."
                primary={(r) => String(r.name || 'Worker')}
                secondary={(r) =>
                  `${r._tag || r.status || ''} · ${r.position || ''} · ${r.department || ''}`
                }
              />
            ) : null}

            {sections.gate_passes ? (
              <SearchableList
                title="Recent gate passes"
                href="/cars?gate_pass=1"
                rows={asRows(sections.gate_passes, ['recent'])}
                empty="No gate passes recorded."
                primary={(r) => String(r.plate_no || r.customer_name || r.document_no || 'Pass')}
                secondary={(r) =>
                  `${r.direction || ''} · ${r.purpose || ''} · ${r.passed_at || ''}`
                }
              />
            ) : null}

            {sections.cash_bank ? (
              <Panel title="Cash / bank breakdown">
                <div className="stat-grid">
                  <div className="stat">
                    <div className="label">Position (asset)</div>
                    <div className="value">
                      <Money value={Number((sections.cash_bank as { position?: number }).position || 0)} />
                    </div>
                  </div>
                  <div className="stat">
                    <div className="label">Cash receipts (all time)</div>
                    <div className="value">
                      <Money
                        value={Number((sections.cash_bank as { cash_receipts?: number }).cash_receipts || 0)}
                      />
                    </div>
                  </div>
                  <div className="stat">
                    <div className="label">Bank / card receipts</div>
                    <div className="value">
                      <Money
                        value={Number((sections.cash_bank as { bank_receipts?: number }).bank_receipts || 0)}
                      />
                    </div>
                  </div>
                </div>
                <p className="muted" style={{ marginTop: 10, fontSize: '0.85rem' }}>
                  Position = all cash received − all expenses. Separate from invoiced revenue and
                  from receivables.
                </p>
              </Panel>
            ) : null}
          </div>

          {(data.unavailable || []).length > 0 ? (
            <p className="muted">Could not load: {(data.unavailable || []).join(', ')}. Try refreshing.</p>
          ) : null}
        </>
      ) : null}
    </div>
  )
}

function ROLE_FROM_USER(role?: string) {
  if (!role) return 'receptionist'
  if (role === 'admin' || role === 'owner' || role === 'manager') return 'manager'
  if (role === 'accountant') return 'accountant'
  if (role === 'technician') return 'technician'
  if (role === 'store_keeper' || role === 'inventory_manager') return 'storekeeper'
  return 'receptionist'
}

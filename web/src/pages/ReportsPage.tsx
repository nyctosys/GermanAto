import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

type Rollup = {
  daily?: Array<Record<string, unknown>>
  monthly?: Array<Record<string, unknown>>
  yearly?: Array<Record<string, unknown>>
  total?: number
  count?: number
}

type ReportsPayload = {
  sales?: Rollup
  expenses?: Rollup
  profit?: Rollup
  receivables?: number
  low_stock?: Array<Record<string, unknown>>
  customer_growth?: Rollup
  invoice_growth?: Rollup
  car_growth?: Rollup
  open_repairs?: Array<Record<string, unknown>>
  vendor_balances?: Array<Record<string, unknown>>
  pending_quotes?: Array<Record<string, unknown>>
  completed_today?: Array<Record<string, unknown>>
  date_range?: { start?: string; end?: string }
  period?: string
  error?: string
}

function isRollup(value: unknown): value is Rollup {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const v = value as Record<string, unknown>
  return 'daily' in v || 'monthly' in v || 'yearly' in v || 'total' in v
}

function RollupSection({ title, data }: { title: string; data: Rollup }) {
  const buckets: Array<{ label: string; rows: Array<Record<string, unknown>> }> = [
    { label: 'Daily', rows: data.daily || [] },
    { label: 'Monthly', rows: data.monthly || [] },
    { label: 'Yearly', rows: data.yearly || [] },
  ]

  return (
    <Panel
      title={title}
      actions={
        typeof data.total === 'number' ? (
          <strong>
            Total: <Money value={data.total} />
          </strong>
        ) : null
      }
    >
      {buckets.every((b) => !b.rows.length) ? (
        <Empty>No {title.toLowerCase()} in this range</Empty>
      ) : (
        buckets.map((bucket) =>
          bucket.rows.length ? (
            <div key={bucket.label} style={{ marginBottom: 16 }}>
              <h3 style={{ fontSize: '0.95rem', margin: '0 0 8px' }}>{bucket.label}</h3>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      {Object.keys(bucket.rows[0]).slice(0, 6).map((col) => (
                        <th key={col}>{col.replaceAll('_', ' ')}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {bucket.rows.slice(0, 31).map((row, idx) => (
                      <tr key={idx}>
                        {Object.keys(bucket.rows[0])
                          .slice(0, 6)
                          .map((col) => (
                            <td key={col}>
                              {typeof row[col] === 'number' &&
                              col !== 'count' &&
                              col !== 'year' &&
                              (col.includes('total') ||
                                col.includes('amount') ||
                                col.includes('price') ||
                                col.includes('balance')) ? (
                                <Money value={row[col] as number} />
                              ) : (
                                String(row[col] ?? '—')
                              )}
                            </td>
                          ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null,
        )
      )}
    </Panel>
  )
}

function ListSection({
  title,
  rows,
  empty,
}: {
  title: string
  rows: Array<Record<string, unknown>>
  empty: string
}) {
  if (!rows.length) {
    return (
      <Panel title={title}>
        <Empty>{empty}</Empty>
      </Panel>
    )
  }
  const cols = Object.keys(rows[0]).slice(0, 8)
  return (
    <Panel title={title}>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {cols.map((col) => (
                <th key={col}>{col.replaceAll('_', ' ')}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 50).map((row, idx) => (
              <tr key={idx}>
                {cols.map((col) => (
                  <td key={col}>
                    {typeof row[col] === 'number' &&
                    (col.includes('total') ||
                      col.includes('amount') ||
                      col.includes('balance') ||
                      col.includes('price') ||
                      col.includes('owed')) ? (
                      <Money value={row[col] as number} />
                    ) : (
                      String(row[col] ?? '—')
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

export function ReportsPage() {
  const today = new Date().toISOString().slice(0, 10)
  const monthStart = today.slice(0, 8) + '01'
  const [from, setFrom] = useState(monthStart)
  const [to, setTo] = useState(today)

  const q = useQuery({
    queryKey: ['reports', from, to],
    queryFn: () =>
      api.get<ReportsPayload>(`/api/reports?start_date=${from}&end_date=${to}`),
  })
  const overdue = useQuery({
    queryKey: ['overdue-payables'],
    queryFn: () =>
      api.get<{ overdue?: Array<Record<string, unknown>>; count?: number }>(
        '/api/reports/overdue-payables',
      ),
  })

  const data = q.data

  return (
    <div>
      <PageHeader
        title="Reports"
        actions={
          <div className="row-actions">
            <input
              type="date"
              className="input"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
            <input
              type="date"
              className="input"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
        }
      />

      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {data?.error ? <ErrorBox error={data.error} /> : null}

      {data ? (
        <>
          <Panel title="Summary">
            <div className="stat-grid">
              <div className="stat">
                <div className="label">Sales</div>
                <div className="value">
                  <Money value={data.sales?.total ?? 0} />
                </div>
              </div>
              <div className="stat">
                <div className="label">Expenses</div>
                <div className="value">
                  <Money value={data.expenses?.total ?? 0} />
                </div>
              </div>
              <div className="stat">
                <div className="label">Profit</div>
                <div className="value">
                  <Money value={data.profit?.total ?? 0} />
                </div>
              </div>
              <div className="stat">
                <div className="label">Receivables</div>
                <div className="value">
                  <Money value={data.receivables ?? 0} />
                </div>
              </div>
            </div>
          </Panel>

          {isRollup(data.sales) ? <RollupSection title="Sales" data={data.sales} /> : null}
          {isRollup(data.expenses) ? (
            <RollupSection title="Expenses" data={data.expenses} />
          ) : null}
          {isRollup(data.profit) ? <RollupSection title="Profit" data={data.profit} /> : null}
          {isRollup(data.invoice_growth) ? (
            <RollupSection title="Invoice growth" data={data.invoice_growth} />
          ) : null}
          {isRollup(data.customer_growth) ? (
            <RollupSection title="Customer growth" data={data.customer_growth} />
          ) : null}
          {isRollup(data.car_growth) ? (
            <RollupSection title="Car growth" data={data.car_growth} />
          ) : null}

          <ListSection
            title="Low stock"
            rows={data.low_stock || []}
            empty="No low-stock items"
          />
          <ListSection
            title="Open repair orders"
            rows={data.open_repairs || []}
            empty="No open repair orders"
          />
          <ListSection
            title="Vendor balances"
            rows={data.vendor_balances || []}
            empty="No vendor balances"
          />
          <ListSection
            title={`Overdue payables (${overdue.data?.count ?? 0})`}
            rows={overdue.data?.overdue || []}
            empty="No overdue supplier invoices"
          />
          <ListSection
            title="Pending quotes"
            rows={data.pending_quotes || []}
            empty="No pending quotes"
          />
          <ListSection
            title="Completed repairs today"
            rows={data.completed_today || []}
            empty="None completed today"
          />
        </>
      ) : null}
    </div>
  )
}

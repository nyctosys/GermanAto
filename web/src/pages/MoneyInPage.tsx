import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { DataTable, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

type MoneyIn = {
  inflow_total: number
  cash_received_total: number
  deposits_applied_total: number
  deposits_liability_open: number
  note?: string
  cash_received: { id: number; date?: string; amount: number; description?: string }[]
  deposits_open: { id: number; amount: number; status: string; visit_id?: number }[]
}

export function MoneyInPage() {
  const q = useQuery({
    queryKey: ['money-in'],
    queryFn: () => api.get<MoneyIn>('/api/money-in?days=30'),
  })

  return (
    <div>
      <PageHeader
        title="Money In"
        actions={
          <Link className="btn btn-secondary" to="/finance/cash-received">
            Cash received
          </Link>
        }
      />
      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {q.data ? (
        <>
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Inflow (30d)</div>
              <div className="value">
                <Money value={q.data.inflow_total} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Cash received</div>
              <div className="value">
                <Money value={q.data.cash_received_total} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Deposits applied</div>
              <div className="value">
                <Money value={q.data.deposits_applied_total} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Open deposit liability</div>
              <div className="value">
                <Money value={q.data.deposits_liability_open} />
              </div>
            </div>
          </div>
          <p className="muted">{q.data.note}</p>
          <Panel title="Recent cash received">
            <DataTable
              columns={[
                { key: 'date', label: 'Date' },
                { key: 'amount', label: 'Amount' },
                { key: 'description', label: 'Description' },
              ]}
              rows={(q.data.cash_received || []).map((r) => ({
                date: r.date || '—',
                amount: <Money value={r.amount} />,
                description: r.description || '—',
              }))}
            />
          </Panel>
          <Panel title="Open customer deposits (liability)">
            <DataTable
              columns={[
                { key: 'id', label: 'ID' },
                { key: 'amount', label: 'Amount' },
                { key: 'visit', label: 'Visit' },
                { key: 'status', label: 'Status' },
              ]}
              rows={(q.data.deposits_open || []).map((d) => ({
                id: d.id,
                amount: <Money value={d.amount} />,
                visit: d.visit_id || '—',
                status: d.status,
              }))}
            />
          </Panel>
        </>
      ) : null}
    </div>
  )
}

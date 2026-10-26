import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { DataTable, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

type MoneyOut = {
  outflow_total: number
  expenses_total: number
  vendor_payments_total: number
  note?: string
  expenses: { id: number; date?: string; category: string; description: string; amount: number }[]
  vendor_payments: { id: number; date?: string; description: string; credit: number }[]
}

export function MoneyOutPage() {
  const q = useQuery({
    queryKey: ['money-out'],
    queryFn: () => api.get<MoneyOut>('/api/money-out?days=30'),
  })

  return (
    <div>
      <PageHeader
        title="Money Out"
        actions={
          <>
            <Link className="btn btn-secondary" to="/finance/daily-expenses">
              Expenses
            </Link>
            <Link className="btn btn-secondary" to="/vendors">
              Vendors
            </Link>
          </>
        }
      />
      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {q.data ? (
        <>
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Outflow (30d)</div>
              <div className="value">
                <Money value={q.data.outflow_total} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Expenses</div>
              <div className="value">
                <Money value={q.data.expenses_total} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Vendor payments</div>
              <div className="value">
                <Money value={q.data.vendor_payments_total} />
              </div>
            </div>
          </div>
          <p className="muted">{q.data.note}</p>
          <Panel title="Expenses">
            <DataTable
              columns={[
                { key: 'date', label: 'Date' },
                { key: 'category', label: 'Category' },
                { key: 'description', label: 'Description' },
                { key: 'amount', label: 'Amount' },
              ]}
              rows={(q.data.expenses || []).map((e) => ({
                date: e.date || '—',
                category: e.category,
                description: e.description,
                amount: <Money value={e.amount} />,
              }))}
            />
          </Panel>
          <Panel title="Vendor payments (ledger credits)">
            <DataTable
              columns={[
                { key: 'date', label: 'Date' },
                { key: 'description', label: 'Description' },
                { key: 'credit', label: 'Paid' },
              ]}
              rows={(q.data.vendor_payments || []).map((v) => ({
                date: v.date || '—',
                description: v.description,
                credit: <Money value={v.credit} />,
              }))}
            />
          </Panel>
        </>
      ) : null}
    </div>
  )
}

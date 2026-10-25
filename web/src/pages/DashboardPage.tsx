import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Empty, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

type DashboardData = {
  sections: Record<string, unknown>
  unavailable?: string[]
  role?: string
  generated_at?: string
}

function asList(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value as Record<string, unknown>[]
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    for (const key of ['items', 'invoices', 'quotes', 'repair_orders', 'expenses', 'workers']) {
      if (Array.isArray(obj[key])) return obj[key] as Record<string, unknown>[]
    }
  }
  return []
}

export function DashboardPage() {
  const { user } = useAuth()
  const q = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardData>('/api/dashboard'),
  })

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.username || ''}`} />
      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {q.data ? (
        <>
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Role</div>
              <div className="value" style={{ textTransform: 'capitalize' }}>
                {(q.data.role || user?.role || '').replaceAll('_', ' ')}
              </div>
            </div>
            <div className="stat">
              <div className="label">Sections</div>
              <div className="value">{Object.keys(q.data.sections || {}).length}</div>
            </div>
          </div>
          {Object.entries(q.data.sections || {}).map(([key, section]) => {
            const rows = asList(section)
            return (
              <Panel key={key} title={key.replaceAll('_', ' ')}>
                {rows.length === 0 ? (
                  <Empty>Nothing pending</Empty>
                ) : (
                  <div className="table-wrap">
                    <table className="data">
                      <thead>
                        <tr>
                          {Object.keys(rows[0])
                            .slice(0, 6)
                            .map((col) => (
                              <th key={col}>{col.replaceAll('_', ' ')}</th>
                            ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rows.slice(0, 8).map((row, idx) => (
                          <tr key={idx}>
                            {Object.keys(rows[0])
                              .slice(0, 6)
                              .map((col) => (
                                <td key={col}>
                                  {typeof row[col] === 'number' &&
                                  /total|amount|balance|price|salary/i.test(col) ? (
                                    <Money value={row[col] as number} />
                                  ) : (
                                    String(row[col] ?? '')
                                  )}
                                </td>
                              ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>
            )
          })}
          <Panel title="Quick links">
            <div className="row-actions">
              <Link className="btn btn-secondary" to="/invoices/new">
                New invoice
              </Link>
              <Link className="btn btn-secondary" to="/inventory">
                Inventory
              </Link>
              <Link className="btn btn-secondary" to="/cars">
                Cars & customers
              </Link>
              <Link className="btn btn-secondary" to="/reports">
                Reports
              </Link>
            </div>
          </Panel>
        </>
      ) : null}
    </div>
  )
}

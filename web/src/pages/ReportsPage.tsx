import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

export function ReportsPage() {
  const today = new Date().toISOString().slice(0, 10)
  const monthStart = today.slice(0, 8) + '01'
  const [from, setFrom] = useState(monthStart)
  const [to, setTo] = useState(today)

  const q = useQuery({
    queryKey: ['reports', from, to],
    queryFn: () =>
      api.get<Record<string, unknown>>(
        `/api/reports?start_date=${from}&end_date=${to}`,
      ),
  })

  const sections = Object.entries(q.data || {}).filter(
    ([, v]) => v !== null && typeof v === 'object',
  )

  return (
    <div>
      <PageHeader title="Reports" />
      <Panel
        title="Date range"
        actions={
          <div className="row-actions">
            <input type="date" className="input" value={from} onChange={(e) => setFrom(e.target.value)} />
            <input type="date" className="input" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        }
      >
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {q.data ? (
          <div className="stat-grid">
            {Object.entries(q.data)
              .filter(([, v]) => typeof v === 'number')
              .map(([k, v]) => (
                <div className="stat" key={k}>
                  <div className="label">{k.replaceAll('_', ' ')}</div>
                  <div className="value">
                    <Money value={v as number} />
                  </div>
                </div>
              ))}
          </div>
        ) : null}
        {!q.isLoading && !sections.length && !q.data ? <Empty /> : null}
        {sections.map(([key, value]) => {
          const rows = Array.isArray(value)
            ? (value as Record<string, unknown>[])
            : Array.isArray((value as Record<string, unknown>).rows)
              ? ((value as Record<string, unknown>).rows as Record<string, unknown>[])
              : Array.isArray((value as Record<string, unknown>).items)
                ? ((value as Record<string, unknown>).items as Record<string, unknown>[])
                : []
          if (!rows.length) {
            return (
              <div key={key} style={{ marginBottom: 16 }}>
                <h2 style={{ fontSize: '1.05rem', marginBottom: 8 }}>{key.replaceAll('_', ' ')}</h2>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>
                  {JSON.stringify(value, null, 2)}
                </pre>
              </div>
            )
          }
          return (
            <div key={key} style={{ marginBottom: 16 }}>
              <h2 style={{ fontSize: '1.05rem', marginBottom: 8 }}>{key.replaceAll('_', ' ')}</h2>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      {Object.keys(rows[0]).slice(0, 8).map((col) => (
                        <th key={col}>{col.replaceAll('_', ' ')}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 50).map((row, idx) => (
                      <tr key={idx}>
                        {Object.keys(rows[0])
                          .slice(0, 8)
                          .map((col) => (
                            <td key={col}>
                              {typeof row[col] === 'number' ? (
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
            </div>
          )
        })}
      </Panel>
    </div>
  )
}

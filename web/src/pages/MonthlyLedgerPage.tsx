import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

export function MonthlyLedgerPage() {
  const now = new Date()
  const [year, setYear] = useState(String(now.getFullYear()))
  const [month, setMonth] = useState(String(now.getMonth() + 1).padStart(2, '0'))

  const q = useQuery({
    queryKey: ['monthly-ledger', year, month],
    queryFn: () =>
      api.get<Record<string, unknown>>(
        `/api/expenses/monthly-ledger?month=${year}-${month.padStart(2, '0')}`,
      ),
  })

  const rows = (() => {
    const data = q.data
    if (!data) return [] as Record<string, unknown>[]
    for (const key of ['entries', 'ledger', 'rows', 'days', 'items']) {
      if (Array.isArray(data[key])) return data[key] as Record<string, unknown>[]
    }
    return []
  })()

  return (
    <div>
      <PageHeader title="Monthly ledger" />
      <Panel
        title="Period"
        actions={
          <div className="row-actions">
            <input
              className="input"
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              style={{ width: 100 }}
            />
            <select className="select" value={month} onChange={(e) => setMonth(e.target.value)}>
              {Array.from({ length: 12 }, (_, i) => {
                const m = String(i + 1).padStart(2, '0')
                return (
                  <option key={m} value={m}>
                    {m}
                  </option>
                )
              })}
            </select>
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
        {!q.isLoading && rows.length === 0 ? <Empty>No ledger rows for this month</Empty> : null}
        {rows.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  {Object.keys(rows[0]).map((col) => (
                    <th key={col}>{col.replaceAll('_', ' ')}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <tr key={idx}>
                    {Object.keys(rows[0]).map((col) => (
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
        ) : null}
      </Panel>
    </div>
  )
}

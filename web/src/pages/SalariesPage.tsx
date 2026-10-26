import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  Money,
  PageHeader,
  Panel,
} from '../components/ui'

type Worker = { id: number; first_name: string; last_name: string; department?: string }

export function SalariesPage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const now = new Date()
  const [year, setYear] = useState(String(now.getFullYear()))
  const [month, setMonth] = useState(String(now.getMonth() + 1).padStart(2, '0'))
  const [workerId, setWorkerId] = useState('')
  const [advance, setAdvance] = useState({ amount: 0, notes: '', date: new Date().toISOString().slice(0, 10) })

  const workers = useQuery({
    queryKey: ['workers'],
    queryFn: () => api.get<Worker[] | { workers: Worker[] }>('/api/workers'),
  })
  const workerList = Array.isArray(workers.data)
    ? workers.data
    : workers.data?.workers || []

  const preview = useQuery({
    queryKey: ['payroll-preview', year, month],
    queryFn: () =>
      api.get<Record<string, unknown>>(
        `/api/salary/payroll/preview?year=${year}&month=${month}`,
      ),
  })

  const advances = useQuery({
    queryKey: ['salary-advances', workerId],
    enabled: !!workerId,
    queryFn: async () => {
      const data = await api.get<{ advances?: Record<string, unknown>[] } | Record<string, unknown>[]>(
        `/api/salary/advances?worker_id=${workerId}`,
      )
      return Array.isArray(data) ? data : data.advances || []
    },
  })

  const runPayroll = useMutation({
    mutationFn: () =>
      api.post('/api/salary/payroll/run', {
        year: Number(year),
        month: Number(month),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['payroll-preview'] }),
  })

  const addAdvance = useMutation({
    mutationFn: () =>
      api.post('/api/salary/advances', {
        worker_id: Number(workerId),
        amount: Number(advance.amount),
        notes: advance.notes,
        date: advance.date,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['salary-advances'] }),
  })

  const previewRows = (() => {
    const data = preview.data
    if (!data) return [] as Record<string, unknown>[]
    for (const key of ['rows', 'employees', 'payroll', 'items']) {
      if (Array.isArray(data[key])) return data[key] as Record<string, unknown>[]
    }
    return []
  })()

  return (
    <div>
      <PageHeader title="Salaries" />
      <Panel
        title="Payroll"
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
            <button
              type="button"
              className="btn"
              disabled={runPayroll.isPending}
              onClick={async () => {
                if (await confirm({ title: 'Run payroll', message: 'Run payroll for this period?', confirmLabel: 'Continue' })) runPayroll.mutate()
              }}
            >
              Run payroll
            </button>
          </div>
        }
      >
        {preview.isLoading ? <Loading /> : null}
        {preview.error ? <ErrorBox error={preview.error} /> : null}
        {runPayroll.error ? <ErrorBox error={runPayroll.error} /> : null}
        {!preview.isLoading && previewRows.length === 0 ? <Empty>No preview rows</Empty> : null}
        {previewRows.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  {Object.keys(previewRows[0]).slice(0, 8).map((col) => (
                    <th key={col}>{col.replaceAll('_', ' ')}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row, idx) => (
                  <tr key={idx}>
                    {Object.keys(previewRows[0])
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
        ) : null}
      </Panel>

      <Panel title="Salary advances">
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addAdvance.mutate()
          }}
        >
          <Field label="Worker">
            <select
              required
              value={workerId}
              onChange={(e) => setWorkerId(e.target.value)}
            >
              <option value="">Select</option>
              {workerList.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.first_name} {w.last_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Date">
            <input
              type="date"
              value={advance.date}
              onChange={(e) => setAdvance({ ...advance, date: e.target.value })}
            />
          </Field>
          <Field label="Amount">
            <input
              type="number"
              value={advance.amount}
              onChange={(e) => setAdvance({ ...advance, amount: Number(e.target.value) })}
            />
          </Field>
          <Field label="Notes">
            <input
              value={advance.notes}
              onChange={(e) => setAdvance({ ...advance, notes: e.target.value })}
            />
          </Field>
          <button className="btn" type="submit" disabled={!workerId || addAdvance.isPending}>
            Add advance
          </button>
        </FormGrid>
        {addAdvance.error ? <ErrorBox error={addAdvance.error} /> : null}
        {(advances.data || []).length > 0 ? (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Amount</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {(advances.data || []).map((row, idx) => (
                  <tr key={Number(row.id) || idx}>
                    <td>{String(row.date || '')}</td>
                    <td>
                      <Money value={Number(row.amount || 0)} />
                    </td>
                    <td>{String(row.notes || '')}</td>
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

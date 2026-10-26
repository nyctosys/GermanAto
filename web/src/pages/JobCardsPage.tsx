import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Empty, ErrorBox, Field, Loading, PageHeader, Panel } from '../components/ui'

type JobCardRow = {
  id: number
  document_no?: string
  customer_name?: string
  customer_reg_no?: string
  status?: string
  priority?: string
  visit_id?: number
  quote_invoice_id?: number
  worker_name?: string
  created_at?: string
}

export function JobCardsPage() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const list = useQuery({
    queryKey: ['job-cards', q, status],
    queryFn: () => {
      const params = new URLSearchParams()
      if (q.trim()) params.set('q', q.trim())
      if (status) params.set('status', status)
      const qs = params.toString()
      return api.get<JobCardRow[]>(`/api/job-cards${qs ? `?${qs}` : ''}`)
    },
  })

  const makeQuote = useMutation({
    mutationFn: (id: number) => api.post(`/api/job-cards/${id}/quote`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job-cards'] }),
  })

  return (
    <div>
      <PageHeader
        title="Job cards"
        actions={
          <Link className="btn" to="/job-cards/new">
            New intake / job card
          </Link>
        }
      />
      <Panel title="Search">
        <div className="form-grid">
          <Field label="Keyword">
            <input
              className="input"
              placeholder="JC no, customer, phone, plate…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </Field>
          <Field label="Status">
            <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="open">Open</option>
              <option value="quoted">Quoted</option>
              <option value="closed">Closed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </Field>
        </div>
      </Panel>
      <Panel title="Open / recent">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {makeQuote.error ? <ErrorBox error={makeQuote.error} /> : null}
        {!list.isLoading && !(list.data || []).length ? <Empty /> : null}
        {(list.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Job card</th>
                  <th>Customer</th>
                  <th>Reg</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Worker</th>
                  <th>Quote</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/job-cards/${r.id}`}>{r.document_no || r.id}</Link>
                    </td>
                    <td>{r.customer_name}</td>
                    <td>{r.customer_reg_no}</td>
                    <td>{r.priority || 'normal'}</td>
                    <td>{r.status}</td>
                    <td>{r.worker_name || '—'}</td>
                    <td>{r.quote_invoice_id || '—'}</td>
                    <td>
                      {!r.quote_invoice_id && r.status !== 'draft' ? (
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => makeQuote.mutate(r.id)}
                        >
                          Create estimate
                        </button>
                      ) : null}
                    </td>
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

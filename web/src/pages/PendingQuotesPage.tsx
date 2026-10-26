import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api/client'
import {
  Empty,
  ErrorBox,
  Loading,
  Money,
  PageHeader,
  Panel,
} from '../components/ui'

type QuoteRow = {
  id: number
  document_no?: string
  customer_name?: string
  customer_reg_no?: string
  status?: string
  approval_state?: string
  net_total?: number
  required_advance?: number
  created_at?: string
}

export function PendingQuotesPage() {
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')

  const q = useQuery({
    queryKey: ['quotes', keyword],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('type', 'quote')
      if (keyword.trim()) params.set('q', keyword.trim())
      const data = await api.get<{ invoices?: QuoteRow[]; quotes?: QuoteRow[] }>(
        `/api/search?${params}`,
      )
      return data.quotes || data.invoices || []
    },
  })

  const convert = useMutation({
    mutationFn: (id: number) => api.post(`/api/invoice/${id}/convert`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes'] }),
  })

  const sendApproval = useMutation({
    mutationFn: (id: number) =>
      api.post<{ approval_url: string }>(`/api/quotes/${id}/send-approval`, {
        public_base_url: window.location.origin,
      }),
  })

  const openRo = useMutation({
    mutationFn: (id: number) => api.post(`/api/repair-orders/from-quote/${id}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes'] }),
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/invoice/${id}/delete`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quotes'] }),
  })

  return (
    <div>
      <PageHeader
        title="Quotes"
        actions={
          <Link className="btn" to="/quotes/new">
            New quote
          </Link>
        }
      />
      <Panel title="Pending / all quotes">
        <div className="form-grid" style={{ marginBottom: 12 }}>
          <input
            className="input"
            placeholder="Search"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {convert.error ? <ErrorBox error={convert.error} /> : null}
        {sendApproval.error ? <ErrorBox error={sendApproval.error} /> : null}
        {openRo.error ? <ErrorBox error={openRo.error} /> : null}
        {sendApproval.data ? (
          <p className="muted">
            Approval link:{' '}
            <a href={sendApproval.data.approval_url}>{sendApproval.data.approval_url}</a>
          </p>
        ) : null}
        {!q.isLoading && !(q.data || []).length ? <Empty /> : null}
        {(q.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Estimate</th>
                  <th>Customer</th>
                  <th>Reg</th>
                  <th>Approval</th>
                  <th>Total</th>
                  <th>Date</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link to={`/quotes/${row.id}`}>{row.document_no || row.id}</Link>
                    </td>
                    <td>{row.customer_name}</td>
                    <td>{row.customer_reg_no}</td>
                    <td>{row.approval_state || row.status}</td>
                    <td>
                      <Money value={row.net_total} />
                    </td>
                    <td>{row.created_at || '—'}</td>
                    <td className="row-actions">
                      <Link className="btn btn-secondary btn-sm" to={`/quotes/${row.id}`}>
                        View
                      </Link>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => sendApproval.mutate(row.id)}
                      >
                        Send approval
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => openRo.mutate(row.id)}
                      >
                        Open RO
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => convert.mutate(row.id)}
                      >
                        Convert
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete quote?')) remove.mutate(row.id)
                        }}
                      >
                        Delete
                      </button>
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

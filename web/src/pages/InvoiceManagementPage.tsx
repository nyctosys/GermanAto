import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
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

type InvoiceRow = {
  id: number
  customer_name?: string
  customer_reg_no?: string
  status?: string
  type_of?: string
  net_total?: number
  balance?: number
  created_at?: string
}

export function InvoiceManagementPage() {
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const [keyword, setKeyword] = useState(sp.get('q') || '')
  const [status, setStatus] = useState(sp.get('status') || 'all')
  const [dateFrom, setDateFrom] = useState(sp.get('start_date') || sp.get('date_from') || '')
  const [dateTo, setDateTo] = useState(sp.get('end_date') || sp.get('date_to') || '')

  const q = useQuery({
    queryKey: ['invoices', keyword, status, dateFrom, dateTo],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('type', 'invoice')
      if (keyword.trim()) params.set('q', keyword.trim())
      if (status !== 'all') params.set('status', status)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      const data = await api.get<{ invoices?: InvoiceRow[] }>(`/api/search?${params}`)
      return data.invoices || []
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/invoice/${id}/delete`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invoices'] }),
  })

  const setStatusMut = useMutation({
    mutationFn: ({ id, status: next }: { id: number; status: string }) =>
      api.put(`/api/invoice/${id}/status`, { status: next }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invoices'] }),
  })

  return (
    <div>
      <PageHeader
        title="Invoices"
        actions={
          <Link className="btn" to="/invoices/new">
            New invoice
          </Link>
        }
      />
      <Panel title="Filters">
        <div className="form-grid">
          <input
            className="input"
            placeholder="Search"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="unpaid">Unpaid</option>
            <option value="partial">Partial</option>
            <option value="paid">Paid</option>
          </select>
          <input
            className="input"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <input
            className="input"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
      </Panel>
      <Panel title="Results">
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {!q.isLoading && !(q.data || []).length ? <Empty /> : null}
        {(q.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Customer</th>
                  <th>Reg</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Balance</th>
                  <th>Date</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.id}</td>
                    <td>{inv.customer_name}</td>
                    <td>{inv.customer_reg_no}</td>
                    <td>{inv.status}</td>
                    <td>
                      <Money value={inv.net_total} />
                    </td>
                    <td>
                      <Money value={inv.balance} />
                    </td>
                    <td>{inv.created_at || '—'}</td>
                    <td className="row-actions">
                      <Link className="btn btn-secondary btn-sm" to={`/invoices/${inv.id}/edit`}>
                        Edit
                      </Link>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setStatusMut.mutate({ id: inv.id, status: 'paid' })}
                      >
                        Mark paid
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete invoice?')) remove.mutate(inv.id)
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

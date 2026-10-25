import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, PageHeader, Panel } from '../components/ui'

type RepairOrder = {
  id: number
  customer_name?: string
  customer_reg_no?: string
  customer_made?: string
  current_status?: string
  worker_name?: string
  created_at?: string
}

export function RepairOrdersPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const q = useQuery({
    queryKey: ['repair-orders', status],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      const data = await api.get<{ repair_orders?: RepairOrder[] } | RepairOrder[]>(
        `/api/repair-orders?${params}`,
      )
      return Array.isArray(data) ? data : data.repair_orders || []
    },
  })

  const updateStatus = useMutation({
    mutationFn: ({ id, status: next }: { id: number; status: string }) =>
      api.put(`/api/repair-orders/${id}/status`, { status: next }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['repair-orders'] }),
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/repair-orders/${id}/delete`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['repair-orders'] }),
  })

  return (
    <div>
      <PageHeader
        title="Repair orders"
        actions={
          <Link className="btn" to="/repair-orders/new">
            New repair order
          </Link>
        }
      />
      <Panel
        title="Orders"
        actions={
          <select
            className="select"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="received">Received</option>
            <option value="in_progress">In progress</option>
            <option value="waiting_parts">Waiting parts</option>
            <option value="completed">Completed</option>
            <option value="delivered">Delivered</option>
          </select>
        }
      >
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
                  <th>Vehicle</th>
                  <th>Status</th>
                  <th>Worker</th>
                  <th>Date</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((ro) => (
                  <tr key={ro.id}>
                    <td>{ro.id}</td>
                    <td>{ro.customer_name}</td>
                    <td>
                      {ro.customer_made} {ro.customer_reg_no}
                    </td>
                    <td>{ro.current_status}</td>
                    <td>{ro.worker_name || '—'}</td>
                    <td>{ro.created_at || '—'}</td>
                    <td className="row-actions">
                      <select
                        className="select"
                        value={ro.current_status || ''}
                        onChange={(e) =>
                          updateStatus.mutate({ id: ro.id, status: e.target.value })
                        }
                      >
                        <option value="received">received</option>
                        <option value="in_progress">in_progress</option>
                        <option value="waiting_parts">waiting_parts</option>
                        <option value="completed">completed</option>
                        <option value="delivered">delivered</option>
                      </select>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete repair order?')) remove.mutate(ro.id)
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

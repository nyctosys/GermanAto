import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import { friendlyDate, friendlyStatus } from '../components/RepairJobFlow'
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

function statusClass(status?: string): string {
  const s = (status || '').toLowerCase()
  if (s === 'in_progress' || s === 'waiting_parts') return 'status-pill is-progress'
  if (s === 'awaiting_qc' || s === 'completed' || s === 'complete' || s === 'delivered')
    return 'status-pill is-ready'
  return 'status-pill'
}

export function RepairOrdersPage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const [sp] = useSearchParams()
  const overdueOnly = sp.get('overdue') === '1'
  const [status, setStatus] = useState(sp.get('status') || '')
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

  const rows = useMemo(() => {
    const list = q.data || []
    if (!overdueOnly) return list
    const cutoff = Date.now() - 7 * 86400000
    return list.filter((ro) => {
      if (!ro.created_at) return false
      const done = (ro.current_status || '').toLowerCase()
      if (done === 'complete' || done === 'completed' || done === 'delivered') return false
      return new Date(ro.created_at).getTime() < cutoff
    })
  }, [q.data, overdueOnly])

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/repair-orders/${id}/delete`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['repair-orders'] }),
  })

  return (
    <div>
      <PageHeader
        title={overdueOnly ? 'Overdue repair orders' : 'Repair orders'}
        actions={
          <Link className="btn" to="/repair-orders/new">
            New repair order
          </Link>
        }
      />

      <Panel
        title={overdueOnly ? 'Open longer than 7 days' : 'Orders'}
        actions={
          <select
            className="select"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="received">Waiting to start</option>
            <option value="in_progress">Work in progress</option>
            <option value="waiting_parts">Waiting for parts</option>
            <option value="awaiting_qc">Ready for check</option>
            <option value="completed">Work finished</option>
            <option value="delivered">Car delivered</option>
          </select>
        }
      >
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {!q.isLoading && !rows.length ? <Empty /> : null}
        {rows.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Customer</th>
                  <th>Vehicle</th>
                  <th>Status</th>
                  <th>Technician</th>
                  <th>Opened</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((ro) => {
                  const st = (ro.current_status || '').toLowerCase()
                  const openTo =
                    st === 'awaiting_qc' || st === 'completed' || st === 'complete'
                      ? `/repair-orders/${ro.id}/pipeline`
                      : `/repair-orders/${ro.id}/execution`
                  return (
                    <tr key={ro.id}>
                      <td>
                        <strong>#{ro.id}</strong>
                      </td>
                      <td>{ro.customer_name}</td>
                      <td>
                        {ro.customer_made}
                        <div className="muted">{ro.customer_reg_no}</div>
                      </td>
                      <td>
                        <span className={statusClass(ro.current_status)}>
                          {friendlyStatus(ro.current_status)}
                        </span>
                      </td>
                      <td>{ro.worker_name || '—'}</td>
                      <td>{friendlyDate(ro.created_at)}</td>
                      <td className="row-actions">
                        <Link className="btn btn-sm" to={openTo}>
                          Open
                        </Link>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={async () => {
                            if (await confirm({ message: `Delete job #${ro.id}?`, danger: true, confirmLabel: 'Delete' })) remove.mutate(ro.id)
                          }}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </div>
  )
}

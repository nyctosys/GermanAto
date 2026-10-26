import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { friendlyDate, friendlyStatus } from '../components/RepairJobFlow'
import { Empty, ErrorBox, Loading, Money, PageHeader, Panel } from '../components/ui'

type Job = {
  id: number
  customer_name?: string
  customer_reg_no?: string
  customer_made?: string
  customer_mileage?: string
  current_status?: string
  worker_name?: string
  due_at?: string | null
  labour_cost_total?: number
  parts_cost_total?: number
  job_cost_total?: number
  progress?: { labour_done: number; labour_total: number; pct: number }
  problem_description?: string | null
}

export function RepairExecutionBoardPage() {
  const [sp] = useSearchParams()
  const workerId = sp.get('worker_id')
  const q = useQuery({
    queryKey: ['repair-execution-jobs', workerId],
    queryFn: () => {
      const params = new URLSearchParams()
      if (workerId) params.set('worker_id', workerId)
      return api.get<{ jobs: Job[] }>(`/api/repair-execution/jobs?${params}`)
    },
  })

  const jobs = q.data?.jobs || []

  return (
    <div>
      <PageHeader
        title="My jobs"
        actions={
          <Link className="btn btn-secondary" to="/repair-orders">
            ← All repair orders
          </Link>
        }
      />
      <Panel title="Open jobs">
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {!q.isLoading && !jobs.length ? <Empty>No open jobs</Empty> : null}
        {jobs.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Vehicle</th>
                  <th>Customer</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Due</th>
                  <th>Cost so far</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td>
                      <strong>#{j.id}</strong>
                    </td>
                    <td>
                      {j.customer_made} {j.customer_reg_no}
                      {j.customer_mileage ? (
                        <div className="muted">{j.customer_mileage} km</div>
                      ) : null}
                    </td>
                    <td>{j.customer_name}</td>
                    <td>
                      <span className="status-pill is-progress">
                        {friendlyStatus(j.current_status)}
                      </span>
                    </td>
                    <td>
                      {j.progress
                        ? `${j.progress.labour_done} of ${j.progress.labour_total} done`
                        : '—'}
                    </td>
                    <td>{friendlyDate(j.due_at)}</td>
                    <td>
                      <Money value={j.job_cost_total || 0} />
                    </td>
                    <td>
                      <Link className="btn btn-sm" to={`/repair-orders/${j.id}/execution`}>
                        Open job →
                      </Link>
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

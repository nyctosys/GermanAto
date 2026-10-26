import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api/client'
import { ErrorBox, Field, Loading, PageHeader, Panel, StatusBadge } from '../components/ui'

type Assignment = {
  id: number
  worker_id: number
  worker_name?: string
  worker_skills?: string[]
  job_card_id?: number
  repair_order_id?: number
  status: string
  priority?: string
  estimated_start_at?: string
  estimated_completion_at?: string
  deadline_at?: string
  is_overdue?: boolean
  override_reason?: string
}

export function SchedulingPage() {
  const qc = useQueryClient()
  const [overdueOnly, setOverdueOnly] = useState(false)
  const [skills, setSkills] = useState('')

  const list = useQuery({
    queryKey: ['assignments-board', overdueOnly],
    queryFn: () =>
      api.get<{ assignments: Assignment[] }>(
        `/api/assignments?${overdueOnly ? 'overdue=1' : ''}`,
      ),
  })

  const suggest = useQuery({
    queryKey: ['schedule-suggest', skills],
    queryFn: () => {
      const q = skills.trim() ? `?skills=${encodeURIComponent(skills.trim())}` : ''
      return api.get<{ workers: Array<Record<string, unknown>> }>(
        `/api/assignments/suggest${q}`,
      )
    },
  })

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.patch(`/api/assignments/${id}`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assignments-board'] }),
  })

  return (
    <div>
      <PageHeader
        title="Worker schedule"
        actions={
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => setOverdueOnly(e.target.checked)}
            />
            Overdue only
          </label>
        }
      />

      <Panel title="Available workers (server)">
        <Field label="Filter by skills">
          <input
            className="input"
            placeholder="electrical,diagnostics"
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
          />
        </Field>
        {suggest.isLoading ? <Loading /> : null}
        {suggest.error ? <ErrorBox error={suggest.error} /> : null}
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Worker</th>
                <th>Skills</th>
                <th>Open</th>
                <th>Available</th>
              </tr>
            </thead>
            <tbody>
              {(suggest.data?.workers || []).slice(0, 15).map((w) => (
                <tr key={String(w.id)}>
                  <td>
                    <Link to={`/hr/employees/${w.id}`}>{String(w.name)}</Link>
                    <div className="muted">{String(w.position || '')}</div>
                  </td>
                  <td>{((w.skills as string[]) || []).join(', ') || '—'}</td>
                  <td>
                    {String(
                      (w.workload as { open_assignment_count?: number })
                        ?.open_assignment_count ?? 0,
                    )}
                  </td>
                  <td>{w.available ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Active & recent assignments">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {setStatus.error ? <ErrorBox error={setStatus.error} /> : null}
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Worker</th>
                <th>Job / RO</th>
                <th>Window</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(list.data?.assignments || []).map((a) => (
                <tr key={a.id}>
                  <td>{a.id}</td>
                  <td>
                    <Link to={`/hr/employees/${a.worker_id}`}>{a.worker_name}</Link>
                    <div className="muted">{(a.worker_skills || []).join(', ')}</div>
                  </td>
                  <td>
                    {a.job_card_id ? (
                      <Link to={`/job-cards/${a.job_card_id}`}>JC-{a.job_card_id}</Link>
                    ) : null}
                    {a.repair_order_id ? (
                      <>
                        {' '}
                        <Link to={`/repair-orders/${a.repair_order_id}/pipeline`}>
                          RO-{a.repair_order_id}
                        </Link>
                      </>
                    ) : null}
                    {a.is_overdue ? (
                      <StatusBadge status="overdue" tone="danger" />
                    ) : null}
                  </td>
                  <td className="muted">
                    {a.estimated_start_at || '—'} → {a.estimated_completion_at || a.deadline_at || '—'}
                    <div>Priority: {a.priority}</div>
                  </td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="row-actions">
                    {a.status === 'assigned' ? (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => setStatus.mutate({ id: a.id, status: 'in_progress' })}
                      >
                        Start
                      </button>
                    ) : null}
                    {a.status === 'in_progress' ? (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => setStatus.mutate({ id: a.id, status: 'completed' })}
                      >
                        Complete
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

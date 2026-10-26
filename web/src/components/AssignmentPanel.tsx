import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { EntitySelect } from './EntitySelect'
import { ErrorBox, Field, Panel } from './ui'

/** API stores "YYYY-MM-DD HH:MM:SS"; datetime-local needs "YYYY-MM-DDTHH:MM". */
function toDatetimeLocal(value?: string | null): string {
  if (!value) return ''
  const t = value.trim().replace(' ', 'T')
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(t)) return t.slice(0, 16)
  return ''
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null
  const normalized = value.replace('T', ' ')
  return normalized.length === 16 ? `${normalized}:00` : normalized
}

type SuggestWorker = {
  id: number
  name: string
  position?: string
  skills?: string[]
  available?: boolean
  suggestion_score?: number
  workload?: {
    open_assignment_count?: number
    open_estimated_hours?: number
    overdue_count?: number
  }
  conflict?: { has_conflict?: boolean }
}

type WorkloadCtx = {
  available?: boolean
  skills?: string[]
  workload?: {
    open_assignment_count?: number
    open_estimated_hours?: number
    overdue_count?: number
    on_leave_today?: boolean
    attendance_today?: { check_in_time?: string } | null
    active_assignments?: Array<{
      id: number
      status: string
      job_card_id?: number
      repair_order_id?: number
      deadline_at?: string
      is_overdue?: boolean
    }>
  }
  note?: string
}

type Props = {
  jobCardId?: number
  repairOrderId?: number
  version?: number
  defaultWorkerId?: number | null
  defaultWorkerLabel?: string
  defaultTeam?: string
  defaultPriority?: string
  defaultDeadline?: string
  onDone?: () => void
}

export function AssignmentPanel({
  jobCardId,
  repairOrderId,
  version,
  defaultWorkerId,
  defaultWorkerLabel,
  defaultTeam,
  defaultPriority = 'normal',
  defaultDeadline,
  onDone,
}: Props) {
  const qc = useQueryClient()
  const [workerId, setWorkerId] = useState(defaultWorkerId ? String(defaultWorkerId) : '')
  const [workerLabel, setWorkerLabel] = useState(defaultWorkerLabel || '')
  const [teamName, setTeamName] = useState(defaultTeam || '')
  const [priority, setPriority] = useState(defaultPriority)
  const [estStart, setEstStart] = useState('')
  const [estEnd, setEstEnd] = useState('')
  const [deadline, setDeadline] = useState(() => toDatetimeLocal(defaultDeadline))
  const [skillsFilter, setSkillsFilter] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [conflictDetail, setConflictDetail] = useState<unknown>(null)

  const suggest = useQuery({
    queryKey: ['assign-suggest', skillsFilter, estStart, estEnd, deadline],
    queryFn: () => {
      const q = new URLSearchParams()
      if (skillsFilter.trim()) q.set('skills', skillsFilter.trim())
      if (estStart) q.set('estimated_start_at', fromDatetimeLocal(estStart) || '')
      if (estEnd) q.set('estimated_completion_at', fromDatetimeLocal(estEnd) || '')
      if (deadline) q.set('deadline_at', fromDatetimeLocal(deadline) || '')
      return api.get<{ workers: SuggestWorker[] }>(`/api/assignments/suggest?${q}`)
    },
  })

  const ctx = useQuery({
    queryKey: ['assign-ctx', workerId],
    enabled: !!workerId,
    queryFn: () => api.get<WorkloadCtx>(`/api/workers/${workerId}/assignment-context`),
  })

  const history = useQuery({
    queryKey: ['assign-history', jobCardId, repairOrderId],
    queryFn: () => {
      const q = new URLSearchParams()
      if (jobCardId) q.set('job_card_id', String(jobCardId))
      if (repairOrderId) q.set('repair_order_id', String(repairOrderId))
      return api.get<{
        assignments: Array<{
          id: number
          worker_name?: string
          status: string
          priority?: string
          estimated_start_at?: string
          estimated_completion_at?: string
          deadline_at?: string
          is_overdue?: boolean
          override_reason?: string
          created_at?: string
        }>
      }>(`/api/assignments?${q}`)
    },
  })

  useEffect(() => {
    if (defaultWorkerId) setWorkerId(String(defaultWorkerId))
    if (defaultWorkerLabel) setWorkerLabel(defaultWorkerLabel)
    if (defaultDeadline) setDeadline(toDatetimeLocal(defaultDeadline))
  }, [defaultWorkerId, defaultWorkerLabel, defaultDeadline])

  const assign = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {
        worker_id: workerId ? Number(workerId) : null,
        job_card_id: jobCardId || null,
        repair_order_id: repairOrderId || null,
        team_name: teamName || null,
        priority,
        estimated_start_at: fromDatetimeLocal(estStart),
        estimated_completion_at: fromDatetimeLocal(estEnd),
        deadline_at: fromDatetimeLocal(deadline),
        override_reason: overrideReason || null,
        version: version ?? null,
      }
      if (jobCardId) {
        return api.post(`/api/job-cards/${jobCardId}/assign-worker`, body, {
          reason: overrideReason || undefined,
        })
      }
      return api.post('/api/assignments', body, {
        reason: overrideReason || undefined,
      })
    },
    onSuccess: () => {
      setConflictDetail(null)
      setOverrideReason('')
      qc.invalidateQueries({ queryKey: ['assign-history'] })
      qc.invalidateQueries({ queryKey: ['job-card', String(jobCardId)] })
      qc.invalidateQueries({ queryKey: ['assign-suggest'] })
      onDone?.()
    },
    onError: (err: unknown) => {
      const e = err as { detail?: { conflict?: unknown; require_reason?: boolean } }
      if (e?.detail && typeof e.detail === 'object' && 'conflict' in e.detail) {
        setConflictDetail(e.detail)
      }
    },
  })

  const wl = ctx.data?.workload

  return (
    <Panel title="Assign worker / schedule">
      {assign.error ? <ErrorBox error={assign.error} /> : null}
      {conflictDetail ? (
        <p className="muted" style={{ color: 'var(--danger, #b33)' }}>
          Conflict detected. Enter an authorized override reason to proceed.
        </p>
      ) : null}

      <div className="form-grid">
        <Field label="Skill filter (suggestions)">
          <input
            className="input"
            placeholder="e.g. electrical,ac"
            value={skillsFilter}
            onChange={(e) => setSkillsFilter(e.target.value)}
          />
        </Field>
        <EntitySelect
          label="Worker"
          type="worker"
          valueId={workerId ? Number(workerId) : null}
          displayValue={workerLabel}
          onSelect={(hit) => {
            if (!hit) {
              setWorkerId('')
              setWorkerLabel('')
              return
            }
            setWorkerId(String(hit.id))
            setWorkerLabel(hit.name || hit.label)
          }}
        />
        <Field label="Team">
          <input className="input" value={teamName} onChange={(e) => setTeamName(e.target.value)} />
        </Field>
        <Field label="Priority">
          <select className="select" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </Field>
        <Field label="Estimated start">
          <input
            className="input"
            type="datetime-local"
            value={estStart}
            onChange={(e) => setEstStart(e.target.value)}
          />
        </Field>
        <Field label="Estimated completion">
          <input
            className="input"
            type="datetime-local"
            value={estEnd}
            onChange={(e) => setEstEnd(e.target.value)}
          />
        </Field>
        <Field label="Deadline">
          <input
            className="input"
            type="datetime-local"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
          />
        </Field>
        {(conflictDetail || (ctx.data && !ctx.data.available)) && (
          <Field label="Override reason (required if conflict)">
            <input
              className="input"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="Authorized reason for overlapping assignment"
            />
          </Field>
        )}
        <button
          type="button"
          className="btn"
          disabled={assign.isPending || !workerId}
          onClick={() => assign.mutate()}
        >
          Save assignment
        </button>
      </div>

      {workerId && ctx.data ? (
        <div style={{ marginTop: 12 }}>
          <p className="muted" style={{ marginBottom: 6 }}>
            Skills: {(ctx.data.skills || []).join(', ') || '—'} ·{' '}
            {ctx.data.available ? 'Available' : 'Not available'} · Open jobs:{' '}
            {wl?.open_assignment_count ?? 0} (~{wl?.open_estimated_hours ?? 0}h)
            {wl?.overdue_count ? ` · Overdue: ${wl.overdue_count}` : ''}
            {wl?.on_leave_today ? ' · On leave today' : ''}
          </p>
          <p className="muted" style={{ fontSize: '0.85em' }}>
            {ctx.data.note}
            {wl?.attendance_today?.check_in_time
              ? ` Attendance today: ${wl.attendance_today.check_in_time} (info only).`
              : ''}
          </p>
          {(wl?.active_assignments || []).length > 0 ? (
            <ul className="muted" style={{ marginTop: 6 }}>
              {wl!.active_assignments!.map((a) => (
                <li key={a.id}>
                  #{a.id} {a.status}
                  {a.job_card_id ? ` JC-${a.job_card_id}` : ''}
                  {a.repair_order_id ? ` RO-${a.repair_order_id}` : ''}
                  {a.is_overdue ? ' (overdue)' : ''}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {suggest.data?.workers?.length ? (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ margin: '0 0 8px' }}>Suggested workers</h4>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Skills</th>
                  <th>Load</th>
                  <th>Avail</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {suggest.data.workers.slice(0, 8).map((w) => (
                  <tr key={w.id}>
                    <td>
                      {w.name}
                      <div className="muted">{w.position}</div>
                    </td>
                    <td>{(w.skills || []).join(', ') || '—'}</td>
                    <td>
                      {w.workload?.open_assignment_count ?? 0} open
                      {w.workload?.overdue_count
                        ? ` / ${w.workload.overdue_count} overdue`
                        : ''}
                    </td>
                    <td>{w.available ? 'Yes' : 'Conflict'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          setWorkerId(String(w.id))
                          setWorkerLabel(w.name)
                        }}
                      >
                        Select
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {history.data?.assignments?.length ? (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ margin: '0 0 8px' }}>Assignment history</h4>
          <ul className="muted">
            {history.data.assignments.map((a) => (
              <li key={a.id}>
                #{a.id} {a.worker_name} — {a.status} / {a.priority}
                {a.deadline_at ? ` · due ${a.deadline_at}` : ''}
                {a.is_overdue ? ' · OVERDUE' : ''}
                {a.override_reason ? ` · override: ${a.override_reason}` : ''}
                {a.created_at ? ` · ${a.created_at}` : ''}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  )
}

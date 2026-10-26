import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import {
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  PageHeader,
  Panel,
} from '../components/ui'

type Worker = {
  id: number
  employee_id?: string
  first_name: string
  last_name: string
  email?: string
  phone?: string
  address?: string
  cnic?: string
  date_of_birth?: string
  hire_date?: string
  position?: string
  department?: string
  salary?: number
  status?: string
  notes?: string
  skills?: string[]
}

export function WorkerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [form, setForm] = useState<Partial<Worker>>({})
  const [skillsText, setSkillsText] = useState('')
  const [leaveForm, setLeaveForm] = useState({
    start_date: '',
    end_date: '',
    leave_type: 'annual',
    notes: '',
  })
  const [workTime, setWorkTime] = useState({
    repair_order_id: '',
    started_at: '',
    ended_at: '',
    hours: '',
    notes: '',
  })

  const detail = useQuery({
    queryKey: ['worker', id],
    enabled: !!id,
    queryFn: () => api.get<Worker | { worker: Worker }>(`/api/workers/${id}`),
  })

  const ctx = useQuery({
    queryKey: ['worker-assign-ctx', id],
    enabled: !!id,
    queryFn: () =>
      api.get<{
        available?: boolean
        workload?: {
          open_assignment_count?: number
          open_estimated_hours?: number
          overdue_count?: number
          actual_repair_hours_total?: number
          on_leave_today?: boolean
        }
        note?: string
      }>(`/api/workers/${id}/assignment-context`),
  })

  const leave = useQuery({
    queryKey: ['worker-leave', id],
    enabled: !!id,
    queryFn: () =>
      api.get<{
        leave: Array<{
          id: number
          start_date: string
          end_date: string
          leave_type: string
          status: string
        }>
      }>(`/api/workers/${id}/leave`),
  })

  const assignments = useQuery({
    queryKey: ['worker-assignments', id],
    enabled: !!id,
    queryFn: () =>
      api.get<{
        assignments: Array<{
          id: number
          status: string
          job_card_id?: number
          repair_order_id?: number
          deadline_at?: string
          is_overdue?: boolean
        }>
      }>(`/api/assignments?worker_id=${id}`),
  })

  const workTimes = useQuery({
    queryKey: ['worker-work-time', id],
    enabled: !!id,
    queryFn: () =>
      api.get<{
        entries: Array<{
          id: number
          repair_order_id?: number
          hours?: number
          started_at?: string
          ended_at?: string
        }>
      }>(`/api/work-time?worker_id=${id}`),
  })

  useEffect(() => {
    if (!detail.data) return
    const w = 'worker' in detail.data ? detail.data.worker : detail.data
    setForm(w)
    setSkillsText((w.skills || []).join(', '))
  }, [detail.data])

  const save = useMutation({
    mutationFn: () =>
      api.put(`/api/workers/${id}`, {
        ...form,
        skills: skillsText
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['worker', id] })
      qc.invalidateQueries({ queryKey: ['worker-assign-ctx', id] })
    },
  })

  const remove = useMutation({
    mutationFn: () => api.delete(`/api/workers/${id}`),
    onSuccess: () => navigate('/hr/employees'),
  })

  const addLeave = useMutation({
    mutationFn: () => api.post(`/api/workers/${id}/leave`, leaveForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['worker-leave', id] })
      qc.invalidateQueries({ queryKey: ['worker-assign-ctx', id] })
      setLeaveForm({ start_date: '', end_date: '', leave_type: 'annual', notes: '' })
    },
  })

  const addWorkTime = useMutation({
    mutationFn: () =>
      api.post('/api/work-time', {
        worker_id: Number(id),
        repair_order_id: workTime.repair_order_id
          ? Number(workTime.repair_order_id)
          : null,
        started_at: workTime.started_at || null,
        ended_at: workTime.ended_at || null,
        hours: workTime.hours ? Number(workTime.hours) : null,
        notes: workTime.notes || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['worker-work-time', id] })
      qc.invalidateQueries({ queryKey: ['worker-assign-ctx', id] })
      setWorkTime({
        repair_order_id: '',
        started_at: '',
        ended_at: '',
        hours: '',
        notes: '',
      })
    },
  })

  if (detail.isLoading) return <Loading />
  if (detail.error) return <ErrorBox error={detail.error} />

  return (
    <div>
      <PageHeader
        title={`${form.first_name || ''} ${form.last_name || ''}`.trim() || `Worker #${id}`}
        actions={
          <>
            <Link className="btn btn-secondary" to="/hr/scheduling">
              Schedule board
            </Link>
            <Link className="btn btn-secondary" to="/hr/employees">
              Back
            </Link>
          </>
        }
      />

      {ctx.data ? (
        <Panel title="Workload & availability">
          <p>
            {ctx.data.available ? 'Available' : 'Not available'} · Open assignments:{' '}
            {ctx.data.workload?.open_assignment_count ?? 0} (~
            {ctx.data.workload?.open_estimated_hours ?? 0}h)
            {ctx.data.workload?.overdue_count
              ? ` · Overdue: ${ctx.data.workload.overdue_count}`
              : ''}
            {ctx.data.workload?.on_leave_today ? ' · On leave today' : ''}
          </p>
          <p className="muted">
            Repair time logged: {ctx.data.workload?.actual_repair_hours_total ?? 0}h (separate
            from attendance). {ctx.data.note}
          </p>
        </Panel>
      ) : null}

      <Panel title="Profile">
        {save.error ? <ErrorBox error={save.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            save.mutate()
          }}
        >
          {(
            [
              ['employee_id', 'Employee ID'],
              ['first_name', 'First name'],
              ['last_name', 'Last name'],
              ['phone', 'Phone'],
              ['email', 'Email'],
              ['department', 'Department'],
              ['position', 'Position'],
              ['address', 'Address'],
              ['cnic', 'CNIC'],
            ] as const
          ).map(([key, label]) => (
            <Field key={key} label={label}>
              <input
                value={String(form[key] || '')}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </Field>
          ))}
          <Field label="Skills (comma-separated)">
            <input
              value={skillsText}
              onChange={(e) => setSkillsText(e.target.value)}
              placeholder="electrical, ac, diagnostics"
            />
          </Field>
          <Field label="Salary">
            <input
              type="number"
              value={form.salary || 0}
              onChange={(e) => setForm({ ...form, salary: Number(e.target.value) })}
            />
          </Field>
          <Field label="Status">
            <select
              value={form.status || 'active'}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              <option value="active">active</option>
              <option value="inactive">inactive</option>
            </select>
          </Field>
          <button className="btn" type="submit" disabled={save.isPending}>
            Save
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => {
              if (confirm('Delete worker?')) remove.mutate()
            }}
          >
            Delete
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Leave">
        {addLeave.error ? <ErrorBox error={addLeave.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addLeave.mutate()
          }}
        >
          <Field label="Start">
            <input
              type="date"
              value={leaveForm.start_date}
              onChange={(e) => setLeaveForm({ ...leaveForm, start_date: e.target.value })}
              required
            />
          </Field>
          <Field label="End">
            <input
              type="date"
              value={leaveForm.end_date}
              onChange={(e) => setLeaveForm({ ...leaveForm, end_date: e.target.value })}
              required
            />
          </Field>
          <Field label="Type">
            <input
              value={leaveForm.leave_type}
              onChange={(e) => setLeaveForm({ ...leaveForm, leave_type: e.target.value })}
            />
          </Field>
          <button className="btn" type="submit" disabled={addLeave.isPending}>
            Add leave
          </button>
        </FormGrid>
        <ul className="muted" style={{ marginTop: 8 }}>
          {(leave.data?.leave || []).map((r) => (
            <li key={r.id}>
              {r.start_date} → {r.end_date} · {r.leave_type} · {r.status}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Assignments">
        <ul className="muted">
          {(assignments.data?.assignments || []).map((a) => (
            <li key={a.id}>
              #{a.id} {a.status}
              {a.job_card_id ? (
                <>
                  {' '}
                  <Link to={`/job-cards/${a.job_card_id}`}>JC-{a.job_card_id}</Link>
                </>
              ) : null}
              {a.repair_order_id ? ` RO-${a.repair_order_id}` : ''}
              {a.is_overdue ? ' OVERDUE' : ''}
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Repair work time (not attendance)">
        {addWorkTime.error ? <ErrorBox error={addWorkTime.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addWorkTime.mutate()
          }}
        >
          <Field label="Repair order ID">
            <input
              value={workTime.repair_order_id}
              onChange={(e) => setWorkTime({ ...workTime, repair_order_id: e.target.value })}
              required
            />
          </Field>
          <Field label="Started">
            <input
              type="datetime-local"
              value={workTime.started_at}
              onChange={(e) => setWorkTime({ ...workTime, started_at: e.target.value })}
            />
          </Field>
          <Field label="Ended">
            <input
              type="datetime-local"
              value={workTime.ended_at}
              onChange={(e) => setWorkTime({ ...workTime, ended_at: e.target.value })}
            />
          </Field>
          <Field label="Hours (optional)">
            <input
              type="number"
              step="0.1"
              value={workTime.hours}
              onChange={(e) => setWorkTime({ ...workTime, hours: e.target.value })}
            />
          </Field>
          <button className="btn" type="submit" disabled={addWorkTime.isPending}>
            Log repair time
          </button>
        </FormGrid>
        <ul className="muted" style={{ marginTop: 8 }}>
          {(workTimes.data?.entries || []).map((e) => (
            <li key={e.id}>
              RO-{e.repair_order_id} · {e.hours ?? '—'}h · {e.started_at} → {e.ended_at}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}

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
  PageHeader,
  Panel,
} from '../components/ui'

type Worker = { id: number; first_name: string; last_name: string }
type Attendance = {
  id: number
  worker_id: number
  worker_name?: string
  date: string
  check_in?: string
  check_out?: string
  status?: string
  notes?: string
}

export function AttendancePage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const today = new Date().toISOString().slice(0, 10)
  const [date, setDate] = useState(today)
  const [form, setForm] = useState({
    worker_id: '',
    date: today,
    check_in: '09:00',
    check_out: '18:00',
    status: 'present',
    notes: '',
  })

  const workers = useQuery({
    queryKey: ['workers'],
    queryFn: () => api.get<Worker[] | { workers: Worker[] }>('/api/workers'),
  })
  const workerList = Array.isArray(workers.data)
    ? workers.data
    : workers.data?.workers || []

  const list = useQuery({
    queryKey: ['attendance', date],
    queryFn: async () => {
      const data = await api.get<Attendance[] | { records: Attendance[] }>(
        `/api/attendance?date=${date}`,
      )
      return Array.isArray(data) ? data : data.records || []
    },
  })

  const save = useMutation({
    mutationFn: () =>
      api.post('/api/attendance', {
        ...form,
        worker_id: Number(form.worker_id),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['attendance'] }),
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/attendance/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['attendance'] }),
  })

  return (
    <div>
      <PageHeader title="Attendance" />
      <Panel title="Record attendance">
        {save.error ? <ErrorBox error={save.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            save.mutate()
          }}
        >
          <Field label="Worker">
            <select
              required
              value={form.worker_id}
              onChange={(e) => setForm({ ...form, worker_id: e.target.value })}
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
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
          </Field>
          <Field label="Check in">
            <input
              type="time"
              value={form.check_in}
              onChange={(e) => setForm({ ...form, check_in: e.target.value })}
            />
          </Field>
          <Field label="Check out">
            <input
              type="time"
              value={form.check_out}
              onChange={(e) => setForm({ ...form, check_out: e.target.value })}
            />
          </Field>
          <Field label="Status">
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              <option value="present">present</option>
              <option value="absent">absent</option>
              <option value="leave">leave</option>
              <option value="half_day">half_day</option>
            </select>
          </Field>
          <button className="btn" type="submit">
            Save
          </button>
        </FormGrid>
      </Panel>
      <Panel
        title="Records"
        actions={
          <input
            type="date"
            className="input"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        }
      >
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && !(list.data || []).length ? <Empty /> : null}
        {(list.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Worker</th>
                  <th>Date</th>
                  <th>In</th>
                  <th>Out</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((row) => (
                  <tr key={row.id}>
                    <td>{row.worker_name || row.worker_id}</td>
                    <td>{row.date}</td>
                    <td>{row.check_in || '—'}</td>
                    <td>{row.check_out || '—'}</td>
                    <td>{row.status}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={async () => {
                          if (await confirm({ message: 'Delete this attendance record?', danger: true, confirmLabel: 'Delete' })) remove.mutate(row.id)
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

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
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
}

export function WorkerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const [form, setForm] = useState<Partial<Worker>>({})

  const detail = useQuery({
    queryKey: ['worker', id],
    enabled: !!id,
    queryFn: () => api.get<Worker | { worker: Worker }>(`/api/workers/${id}`),
  })

  useEffect(() => {
    if (!detail.data) return
    const w = 'worker' in detail.data ? detail.data.worker : detail.data
    setForm(w)
  }, [detail.data])

  const save = useMutation({
    mutationFn: () => api.put(`/api/workers/${id}`, form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['worker', id] }),
  })

  const remove = useMutation({
    mutationFn: () => api.delete(`/api/workers/${id}`),
    onSuccess: () => navigate('/hr/employees'),
  })

  if (detail.isLoading) return <Loading />
  if (detail.error) return <ErrorBox error={detail.error} />

  return (
    <div>
      <PageHeader
        title={`${form.first_name || ''} ${form.last_name || ''}`.trim() || `Worker #${id}`}
        actions={
          <Link className="btn btn-secondary" to="/hr/employees">
            Back
          </Link>
        }
      />
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
            onClick={async () => {
              if (await confirm({ message: 'Delete this worker?', danger: true, confirmLabel: 'Delete' })) remove.mutate()
            }}
          >
            Delete
          </button>
        </FormGrid>
      </Panel>
    </div>
  )
}

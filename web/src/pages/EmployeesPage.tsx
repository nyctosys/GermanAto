import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  Money,
  PageHeader,
  Panel,
} from '../components/ui'

type Worker = {
  id: number
  employee_id?: string
  first_name: string
  last_name: string
  phone?: string
  department?: string
  position?: string
  salary?: number
  status?: string
}

const empty = {
  employee_id: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  address: '',
  cnic: '',
  date_of_birth: '',
  hire_date: new Date().toISOString().slice(0, 10),
  position: '',
  department: '',
  salary: 0,
  status: 'active',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  notes: '',
}

export function EmployeesPage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const [form, setForm] = useState(empty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)

  const list = useQuery({
    queryKey: ['workers'],
    queryFn: () => api.get<Worker[] | { workers: Worker[] }>('/api/workers'),
  })
  const departments = useQuery({
    queryKey: ['departments'],
    queryFn: () =>
      api.get<{ id: number; name: string }[] | { departments: { name: string }[] }>(
        '/api/settings/departments',
      ),
  })
  const deptNames = Array.isArray(departments.data)
    ? departments.data.map((d) => ('name' in d ? d.name : String(d)))
    : (departments.data?.departments || []).map((d) => d.name)

  const workers = Array.isArray(list.data) ? list.data : list.data?.workers || []

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        ...form,
        salary: form.salary ? Number(form.salary) : null,
        email: form.email || null,
      }
      if (editingId) return api.put(`/api/workers/${editingId}`, body)
      return api.post('/api/workers', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workers'] })
      setForm(empty)
      setEditingId(null)
      setShowForm(false)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/workers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workers'] }),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div>
      <PageHeader
        title="Employees"
        actions={
          <button type="button" className="btn" onClick={() => setShowForm(true)}>
            Add employee
          </button>
        }
      />
      {showForm ? (
        <Panel title={editingId ? 'Edit employee' : 'New employee'}>
          {save.error ? <ErrorBox error={save.error} /> : null}
          <FormGrid onSubmit={onSubmit}>
            <Field label="Employee ID">
              <input
                required
                value={form.employee_id}
                onChange={(e) => setForm({ ...form, employee_id: e.target.value })}
              />
            </Field>
            <Field label="First name">
              <input
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
            </Field>
            <Field label="Last name">
              <input
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </Field>
            <Field label="Phone">
              <input
                required
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </Field>
            <Field label="CNIC">
              <input
                required
                value={form.cnic}
                onChange={(e) => setForm({ ...form, cnic: e.target.value })}
              />
            </Field>
            <Field label="Hire date">
              <input
                type="date"
                required
                value={form.hire_date}
                onChange={(e) => setForm({ ...form, hire_date: e.target.value })}
              />
            </Field>
            <Field label="DOB">
              <input
                type="date"
                value={form.date_of_birth}
                onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
              />
            </Field>
            <Field label="Position">
              <input
                required
                value={form.position}
                onChange={(e) => setForm({ ...form, position: e.target.value })}
              />
            </Field>
            <Field label="Department">
              <input
                required
                list="dept-list"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
              <datalist id="dept-list">
                {deptNames.map((d) => (
                  <option key={d} value={d} />
                ))}
              </datalist>
            </Field>
            <Field label="Salary">
              <input
                type="number"
                value={form.salary}
                onChange={(e) => setForm({ ...form, salary: Number(e.target.value) })}
              />
            </Field>
            <Field label="Address">
              <input
                required
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
              />
            </Field>
            <Field label="Status">
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                <option value="active">active</option>
                <option value="inactive">inactive</option>
              </select>
            </Field>
            <button className="btn" type="submit" disabled={save.isPending}>
              Save
            </button>
          </FormGrid>
        </Panel>
      ) : null}
      <Panel title="Workers">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && workers.length === 0 ? <Empty /> : null}
        {workers.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Dept</th>
                  <th>Position</th>
                  <th>Salary</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {workers.map((w) => (
                  <tr key={w.id}>
                    <td>{w.employee_id || w.id}</td>
                    <td>
                      <Link to={`/hr/employees/${w.id}`}>
                        {w.first_name} {w.last_name}
                      </Link>
                    </td>
                    <td>{w.department}</td>
                    <td>{w.position}</td>
                    <td>
                      <Money value={w.salary} />
                    </td>
                    <td>{w.status}</td>
                    <td className="row-actions">
                      <Link className="btn btn-secondary btn-sm" to={`/hr/employees/${w.id}`}>
                        Open
                      </Link>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={async () => {
                          if (await confirm({ message: 'Delete this worker?', danger: true, confirmLabel: 'Delete' })) remove.mutate(w.id)
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

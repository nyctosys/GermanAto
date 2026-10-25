import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import {
  ErrorBox,
  Field,
  FormGrid,
  PageHeader,
  Panel,
} from '../components/ui'

type Worker = { id: number; first_name: string; last_name: string }
type PartLine = { description: string; quantity: number; part_number: string }
type LabourLine = { description: string }

const empty = {
  customer_name: '',
  customer_phone: '',
  customer_address: '',
  customer_reg_no: '',
  customer_made: '',
  customer_mileage: '',
  customer_vin: '',
  customer_color: '',
  customer_chasis: '',
  problem_description: '',
  worker_ids: [] as number[],
}

export function RepairOrderCreatePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(empty)
  const [parts, setParts] = useState<PartLine[]>([
    { description: '', quantity: 1, part_number: '' },
  ])
  const [labour, setLabour] = useState<LabourLine[]>([{ description: '' }])

  const workers = useQuery({
    queryKey: ['assignable-workers'],
    queryFn: () =>
      api.get<{ workers?: Worker[] } | Worker[]>(
        '/api/repair-orders/assignable-workers',
      ),
  })
  const workerList = Array.isArray(workers.data)
    ? workers.data
    : workers.data?.workers || []

  const create = useMutation({
    mutationFn: () =>
      api.post<{ repair_order_id: number }>('/api/repair-orders', {
        ...form,
        parts: parts.filter((p) => p.description),
        labour: labour.filter((l) => l.description),
      }),
    onSuccess: () => navigate('/repair-orders'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }

  return (
    <div>
      <PageHeader title="New repair order" />
      {create.error ? <ErrorBox error={create.error} /> : null}
      <form onSubmit={onSubmit} className="stack">
        <Panel title="Customer & vehicle">
          <FormGrid>
            <Field label="Customer name">
              <input
                required
                value={form.customer_name}
                onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
              />
            </Field>
            <Field label="Phone">
              <input
                value={form.customer_phone}
                onChange={(e) => setForm({ ...form, customer_phone: e.target.value })}
              />
            </Field>
            <Field label="Address">
              <input
                value={form.customer_address}
                onChange={(e) => setForm({ ...form, customer_address: e.target.value })}
              />
            </Field>
            <Field label="Reg no">
              <input
                value={form.customer_reg_no}
                onChange={(e) => setForm({ ...form, customer_reg_no: e.target.value })}
              />
            </Field>
            <Field label="Make / model">
              <input
                value={form.customer_made}
                onChange={(e) => setForm({ ...form, customer_made: e.target.value })}
              />
            </Field>
            <Field label="Mileage">
              <input
                value={form.customer_mileage}
                onChange={(e) => setForm({ ...form, customer_mileage: e.target.value })}
              />
            </Field>
            <Field label="Problem">
              <textarea
                className="textarea"
                value={form.problem_description}
                onChange={(e) =>
                  setForm({ ...form, problem_description: e.target.value })
                }
              />
            </Field>
            <Field label="Workers">
              <select
                multiple
                value={form.worker_ids.map(String)}
                onChange={(e) =>
                  setForm({
                    ...form,
                    worker_ids: Array.from(e.target.selectedOptions).map((o) =>
                      Number(o.value),
                    ),
                  })
                }
                style={{ minHeight: 90 }}
              >
                {workerList.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.first_name} {w.last_name}
                  </option>
                ))}
              </select>
            </Field>
          </FormGrid>
        </Panel>
        <Panel
          title="Parts"
          actions={
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() =>
                setParts([...parts, { description: '', quantity: 1, part_number: '' }])
              }
            >
              Add part
            </button>
          }
        >
          {parts.map((p, idx) => (
            <div className="line-item" key={idx}>
              <Field label="Description">
                <input
                  value={p.description}
                  onChange={(e) => {
                    const next = [...parts]
                    next[idx] = { ...p, description: e.target.value }
                    setParts(next)
                  }}
                />
              </Field>
              <Field label="Qty">
                <input
                  type="number"
                  value={p.quantity}
                  onChange={(e) => {
                    const next = [...parts]
                    next[idx] = { ...p, quantity: Number(e.target.value) }
                    setParts(next)
                  }}
                />
              </Field>
              <Field label="Part #">
                <input
                  value={p.part_number}
                  onChange={(e) => {
                    const next = [...parts]
                    next[idx] = { ...p, part_number: e.target.value }
                    setParts(next)
                  }}
                />
              </Field>
            </div>
          ))}
        </Panel>
        <Panel
          title="Labour"
          actions={
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setLabour([...labour, { description: '' }])}
            >
              Add labour
            </button>
          }
        >
          {labour.map((l, idx) => (
            <Field key={idx} label="Description">
              <input
                value={l.description}
                onChange={(e) => {
                  const next = [...labour]
                  next[idx] = { description: e.target.value }
                  setLabour(next)
                }}
              />
            </Field>
          ))}
        </Panel>
        <button className="btn" type="submit" disabled={create.isPending}>
          {create.isPending ? 'Creating…' : 'Create repair order'}
        </button>
      </form>
    </div>
  )
}

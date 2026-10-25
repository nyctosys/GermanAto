import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
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
type Visit = {
  id: number
  odometer?: string
  reported_complaints?: string
  repair_order_id?: number | null
  check_in_at?: string
}
type CarRow = {
  id: number
  make?: string
  model?: string
  plate_no?: string
  customer_name?: string
  customer_phone?: string
  mileage?: string
}

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
  car_id: '' as string | number,
  visit_id: '' as string | number,
}

export function RepairOrderCreatePage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [form, setForm] = useState({
    ...empty,
    car_id: params.get('car_id') || '',
    visit_id: params.get('visit_id') || '',
  })
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

  const carIdNum = Number(form.car_id)
  const visits = useQuery({
    queryKey: ['car-visits', form.car_id],
    enabled: Number.isFinite(carIdNum) && carIdNum > 0,
    queryFn: () =>
      api.get<{ visits: Visit[] }>(`/api/cars/${carIdNum}/visits`),
  })

  useEffect(() => {
    const carId = params.get('car_id')
    const visitId = params.get('visit_id')
    if (!carId) return
    api.get<CarRow>(`/api/cars/${carId}`).then((car) => {
      setForm((prev) => ({
        ...prev,
        car_id: carId,
        visit_id: visitId || prev.visit_id,
        customer_name: car.customer_name || prev.customer_name,
        customer_phone: car.customer_phone || prev.customer_phone,
        customer_reg_no: car.plate_no || prev.customer_reg_no,
        customer_made: `${car.make || ''} ${car.model || ''}`.trim(),
        customer_mileage: car.mileage || prev.customer_mileage,
      }))
    }).catch(() => undefined)
  }, [params])

  useEffect(() => {
    const visitId = Number(form.visit_id)
    const list = visits.data?.visits || []
    const visit = list.find((v) => v.id === visitId)
    if (!visit) return
    setForm((prev) => ({
      ...prev,
      customer_mileage: visit.odometer || prev.customer_mileage,
      problem_description: visit.reported_complaints || prev.problem_description,
    }))
  }, [form.visit_id, visits.data])

  const create = useMutation({
    mutationFn: () =>
      api.post<{ repair_order_id: number }>('/api/repair-orders', {
        ...form,
        car_id: form.car_id ? Number(form.car_id) : null,
        visit_id: form.visit_id ? Number(form.visit_id) : null,
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
        <Panel title="Check-in link">
          <p className="muted">
            If this job is for a registered car, a completed check-in (signature +
            inspection) is required. Walk-ins without a car record can leave car/visit blank.
          </p>
          <FormGrid>
            <Field label="Car id">
              <input
                value={String(form.car_id || '')}
                onChange={(e) => setForm({ ...form, car_id: e.target.value, visit_id: '' })}
                placeholder="Optional unless registered car"
              />
            </Field>
            <Field label="Check-in visit">
              <select
                value={String(form.visit_id || '')}
                onChange={(e) => setForm({ ...form, visit_id: e.target.value })}
                disabled={!form.car_id}
              >
                <option value="">Select completed check-in</option>
                {(visits.data?.visits || [])
                  .filter((v) => !v.repair_order_id)
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      #{v.id} · {v.check_in_at || '—'} · odo {v.odometer || '—'}
                    </option>
                  ))}
              </select>
            </Field>
            {form.car_id ? (
              <Link className="btn btn-secondary btn-sm" to={`/cars/${form.car_id}?tab=checkin`}>
                Open check-in on car
              </Link>
            ) : null}
          </FormGrid>
        </Panel>
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

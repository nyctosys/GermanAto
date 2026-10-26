import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  getCustomerBundle,
  type CustomerActivity,
  type EntityHit,
} from '../api/entities'
import { EntitySelect } from '../components/EntitySelect'
import { ErrorBox, Field, FormGrid, Money, PageHeader, Panel } from '../components/ui'

type LabourCode = {
  id: number
  code: string
  description: string
  standard_hours: number
  rate: number
}
type InvItem = {
  id: number
  name: string
  part_number?: string
  price?: number
  quantity?: number
}
type CarRow = {
  id: number
  make?: string
  model?: string
  plate_no?: string
  mileage?: string
  vin?: string
  customer_id?: number
  customer_name?: string
  customer_phone?: string
}
type VisitRow = {
  id: number
  odometer?: string
  fuel_level?: string
  reported_complaints?: string
  existing_damage?: string
  check_in_at?: string
  status?: string
}
type Line = {
  line_type: 'labour' | 'part'
  labour_code_id?: number
  inventory_id?: number
  description: string
  quantity: number
  unit_price: number
  std_hours?: number
  pay_type: string
  assigned_technician?: string
  line_status: string
  part_number?: string
}

function localNowInput() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function JobCardCreatePage() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [customer_name, setName] = useState('')
  const [customer_phone, setPhone] = useState('')
  const [customer_reg_no, setReg] = useState('')
  const [customer_made, setMade] = useState('')
  const [visit_id, setVisitId] = useState(params.get('visit_id') || '')
  const [car_id, setCarId] = useState(params.get('car_id') || '')
  const [customer_id, setCustomerId] = useState(params.get('customer_id') || '')
  const [lines, setLines] = useState<Line[]>([])
  const [invQ, setInvQ] = useState('')
  const [activity, setActivity] = useState<CustomerActivity | null>(null)
  const [problem, setProblem] = useState('')
  const [inspectionNotes, setInspectionNotes] = useState('')
  const [odometer, setOdometer] = useState('')
  const [fuel, setFuel] = useState('')
  const [priority, setPriority] = useState('normal')
  const [intakeAt, setIntakeAt] = useState(localNowInput())
  const [deadline, setDeadline] = useState('')
  const [workerId, setWorkerId] = useState('')
  const [workerLabel, setWorkerLabel] = useState('')
  const [teamName, setTeamName] = useState('')
  const [status, setStatus] = useState<'draft' | 'open'>('open')
  const [showNewCustomer, setShowNewCustomer] = useState(false)
  const [showNewVehicle, setShowNewVehicle] = useState(false)
  const [newCust, setNewCust] = useState({ name: '', phone: '', address: '' })
  const [newVeh, setNewVeh] = useState({ plate_no: '', make: '', model: '', year: '', vin: '' })
  const [visits, setVisits] = useState<VisitRow[]>([])

  const codes = useQuery({
    queryKey: ['labour-codes'],
    queryFn: () => api.get<LabourCode[]>('/api/labour-codes'),
  })

  const inventory = useQuery({
    queryKey: ['inv-picker', invQ],
    queryFn: async () => {
      const data = await api.get<{ items?: InvItem[] } | InvItem[]>(
        `/api/inventory?q=${encodeURIComponent(invQ)}&limit=20`,
      )
      if (Array.isArray(data)) return data
      return data.items || []
    },
  })

  function applyVisit(v: VisitRow) {
    setVisitId(String(v.id))
    if (v.odometer) setOdometer(v.odometer)
    if (v.fuel_level) setFuel(v.fuel_level)
    if (v.reported_complaints) setProblem(v.reported_complaints)
    if (v.existing_damage) setInspectionNotes(v.existing_damage)
    if (v.check_in_at) {
      setIntakeAt(v.check_in_at.replace(' ', 'T').slice(0, 16))
    }
  }

  async function loadVisitsForCar(carId: string) {
    try {
      const data = await api.get<{ visits?: VisitRow[] }>(`/api/cars/${carId}/visits`)
      const rows = data.visits || []
      setVisits(rows)
      const preferred = params.get('visit_id')
      const hit = preferred
        ? rows.find((v) => String(v.id) === preferred)
        : rows[0]
      if (hit) applyVisit(hit)
    } catch {
      setVisits([])
    }
  }

  useEffect(() => {
    const carId = params.get('car_id')
    const visitId = params.get('visit_id')
    const customerId = params.get('customer_id')
    if (customerId && !carId) {
      void getCustomerBundle(Number(customerId))
        .then((bundle) => {
          const c = bundle.customer
          setActivity(bundle.activity || null)
          setCustomerId(String(c.id))
          setName(c.name || '')
          setPhone(c.phone || '')
        })
        .catch(() => undefined)
    }
    if (!carId) return
    api
      .get<CarRow>(`/api/cars/${carId}`)
      .then((car) => {
        setCarId(carId)
        if (visitId) setVisitId(visitId)
        if (car.customer_id) setCustomerId(String(car.customer_id))
        setName(car.customer_name || '')
        setPhone(car.customer_phone || '')
        setReg(car.plate_no || '')
        setMade(`${car.make || ''} ${car.model || ''}`.trim())
        if (car.mileage) setOdometer(car.mileage)
        if (car.customer_id) {
          void getCustomerBundle(car.customer_id).then((b) =>
            setActivity(b.activity || null),
          )
        }
        void loadVisitsForCar(carId)
      })
      .catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  async function onPickCustomer(hit: EntityHit | null) {
    if (!hit) {
      setCustomerId('')
      setActivity(null)
      return
    }
    const bundle = await getCustomerBundle(hit.id)
    const c = bundle.customer
    setActivity(bundle.activity || null)
    setCustomerId(String(c.id))
    setName(c.name || hit.name || '')
    setPhone(c.phone || hit.phone || '')
    if (car_id) {
      const vehicles = bundle.vehicles || []
      if (!vehicles.some((v) => v.id === Number(car_id))) {
        setCarId('')
        setReg('')
        setMade('')
        setVisits([])
        setVisitId('')
      }
    }
  }

  async function onPickCar(hit: EntityHit | null) {
    if (!hit) {
      setCarId('')
      setVisits([])
      return
    }
    setCarId(String(hit.id))
    setReg(hit.plate_no || '')
    setMade(`${hit.make || ''} ${hit.model || ''}`.trim())
    if (hit.customer_id) {
      setCustomerId(String(hit.customer_id))
      const bundle = await getCustomerBundle(hit.customer_id)
      setActivity(bundle.activity || null)
      setName(bundle.customer.name || hit.customer_name || '')
      setPhone(bundle.customer.phone || hit.customer_phone || '')
    }
    void loadVisitsForCar(String(hit.id))
  }

  const createCustomer = useMutation({
    mutationFn: () =>
      api.post<{ customer: { id: number; name?: string; phone?: string } }>('/api/customers', {
        name: newCust.name,
        phone: newCust.phone,
        address: newCust.address || null,
        customer_type: 'walk_in',
      }),
    onSuccess: (res) => {
      const c = res.customer
      setCustomerId(String(c.id))
      setName(c.name || newCust.name)
      setPhone(c.phone || newCust.phone)
      setShowNewCustomer(false)
      void getCustomerBundle(c.id).then((b) => setActivity(b.activity || null))
    },
  })

  const createVehicle = useMutation({
    mutationFn: () =>
      api.post<{ car: CarRow; reused?: boolean }>('/api/cars', {
        customer_id: customer_id ? Number(customer_id) : null,
        plate_no: newVeh.plate_no || null,
        make: newVeh.make || null,
        model: newVeh.model || null,
        year: newVeh.year ? Number(newVeh.year) : null,
        vin: newVeh.vin || null,
      }),
    onSuccess: (res) => {
      const car = res.car
      setCarId(String(car.id))
      setReg(car.plate_no || newVeh.plate_no)
      setMade(`${car.make || newVeh.make} ${car.model || newVeh.model}`.trim())
      setShowNewVehicle(false)
      void loadVisitsForCar(String(car.id))
    },
  })

  function payload(nextStatus: 'draft' | 'open') {
    return {
      customer_name,
      customer_phone,
      customer_reg_no,
      customer_made,
      visit_id: visit_id ? Number(visit_id) : null,
      car_id: car_id ? Number(car_id) : null,
      customer_id: customer_id ? Number(customer_id) : null,
      problem_description: problem || null,
      inspection_notes: inspectionNotes || null,
      odometer: odometer || null,
      fuel_level: fuel || null,
      priority,
      intake_at: intakeAt ? intakeAt.replace('T', ' ') + ':00' : null,
      expected_completion_at: deadline
        ? (() => {
            const n = deadline.replace('T', ' ')
            return n.length === 16 ? `${n}:00` : n
          })()
        : null,
      worker_id: workerId ? Number(workerId) : null,
      team_name: teamName || null,
      status: nextStatus,
      lines,
    }
  }

  const create = useMutation({
    mutationFn: (nextStatus: 'draft' | 'open') =>
      api.post<{ id: number }>('/api/job-cards', payload(nextStatus)),
    onSuccess: (row) => nav(`/job-cards/${row.id}?created=1`),
  })

  const invOptions = useMemo(() => inventory.data || [], [inventory.data])

  function addLabour(code?: LabourCode) {
    setLines((prev) => [
      ...prev,
      {
        line_type: 'labour',
        labour_code_id: code?.id,
        description: code?.description || '',
        quantity: 1,
        unit_price: code?.rate || 0,
        std_hours: code?.standard_hours,
        pay_type: 'customer',
        line_status: 'Pending',
      },
    ])
  }

  function addPart(item: InvItem) {
    setLines((prev) => [
      ...prev,
      {
        line_type: 'part',
        inventory_id: item.id,
        description: item.name,
        quantity: 1,
        unit_price: Number(item.price || 0),
        pay_type: 'customer',
        line_status: 'Pending',
        part_number: item.part_number,
      },
    ])
  }

  return (
    <div>
      <PageHeader title="Vehicle intake / job card" />
      <Panel title="Customer & vehicle">
        {create.error ? <ErrorBox error={create.error} /> : null}
        <p className="muted">
          Search saved customers/vehicles first. Permanent IDs are linked — opening a job card
          does not create duplicates.
        </p>
        {activity ? (
          <div className="stat-grid" style={{ marginBottom: 12 }}>
            <div className="stat">
              <div className="label">Balance due</div>
              <div className="value">
                <Money value={activity.receivable_total || 0} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Prior repairs</div>
              <div className="value">{activity.counts?.repairs || 0}</div>
            </div>
            <div className="stat">
              <div className="label">Estimates</div>
              <div className="value">{activity.counts?.estimates || 0}</div>
            </div>
          </div>
        ) : null}
        <div className="form-grid">
          <EntitySelect
            label="Customer"
            type="customer"
            valueId={customer_id ? Number(customer_id) : null}
            displayValue={
              customer_name ? `${customer_name} · ${customer_phone || ''}`.trim() : ''
            }
            onSelect={(hit) => {
              void onPickCustomer(hit)
            }}
          />
          <EntitySelect
            label="Vehicle"
            type="car"
            valueId={car_id ? Number(car_id) : null}
            customerId={customer_id ? Number(customer_id) : null}
            displayValue={
              customer_reg_no || customer_made
                ? `${customer_reg_no} · ${customer_made}`.trim()
                : ''
            }
            placeholder={
              customer_id ? 'Search this customer’s vehicles…' : 'Search plate / VIN / make…'
            }
            onSelect={(hit) => {
              void onPickCar(hit)
            }}
          />
          <Field label="Customer name">
            <input className="input" value={customer_name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Phone">
            <input className="input" value={customer_phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>
          <Field label="Reg no">
            <input className="input" value={customer_reg_no} onChange={(e) => setReg(e.target.value)} />
          </Field>
          <Field label="Make / model">
            <input className="input" value={customer_made} onChange={(e) => setMade(e.target.value)} />
          </Field>
        </div>
        <div className="row-actions" style={{ marginTop: 8 }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowNewCustomer((v) => !v)}>
            {showNewCustomer ? 'Hide new customer' : 'New customer'}
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowNewVehicle((v) => !v)}
            disabled={!customer_id && !customer_name}
          >
            {showNewVehicle ? 'Hide new vehicle' : 'Register vehicle'}
          </button>
          {car_id ? (
            <Link className="btn btn-ghost btn-sm" to={`/cars/${car_id}?tab=checkin`}>
              Full check-in / photos
            </Link>
          ) : null}
        </div>
        {showNewCustomer ? (
          <FormGrid
            onSubmit={(e) => {
              e.preventDefault()
              createCustomer.mutate()
            }}
          >
            {createCustomer.error ? <ErrorBox error={createCustomer.error} /> : null}
            <Field label="Name">
              <input
                className="input"
                value={newCust.name}
                onChange={(e) => setNewCust({ ...newCust, name: e.target.value })}
                required
              />
            </Field>
            <Field label="Phone">
              <input
                className="input"
                value={newCust.phone}
                onChange={(e) => setNewCust({ ...newCust, phone: e.target.value })}
                required
              />
            </Field>
            <Field label="Address">
              <input
                className="input"
                value={newCust.address}
                onChange={(e) => setNewCust({ ...newCust, address: e.target.value })}
              />
            </Field>
            <button className="btn" type="submit" disabled={createCustomer.isPending}>
              Save customer
            </button>
          </FormGrid>
        ) : null}
        {showNewVehicle ? (
          <FormGrid
            onSubmit={(e) => {
              e.preventDefault()
              createVehicle.mutate()
            }}
          >
            {createVehicle.error ? <ErrorBox error={createVehicle.error} /> : null}
            <Field label="Plate">
              <input
                className="input"
                value={newVeh.plate_no}
                onChange={(e) => setNewVeh({ ...newVeh, plate_no: e.target.value })}
                required
              />
            </Field>
            <Field label="Make">
              <input
                className="input"
                value={newVeh.make}
                onChange={(e) => setNewVeh({ ...newVeh, make: e.target.value })}
              />
            </Field>
            <Field label="Model">
              <input
                className="input"
                value={newVeh.model}
                onChange={(e) => setNewVeh({ ...newVeh, model: e.target.value })}
              />
            </Field>
            <Field label="Year">
              <input
                className="input"
                value={newVeh.year}
                onChange={(e) => setNewVeh({ ...newVeh, year: e.target.value })}
              />
            </Field>
            <Field label="VIN">
              <input
                className="input"
                value={newVeh.vin}
                onChange={(e) => setNewVeh({ ...newVeh, vin: e.target.value })}
              />
            </Field>
            <button className="btn" type="submit" disabled={createVehicle.isPending}>
              Save vehicle
            </button>
          </FormGrid>
        ) : null}
      </Panel>

      <Panel title="Intake">
        <div className="form-grid">
          <Field label="Check-in visit">
            <select
              className="select"
              value={visit_id}
              onChange={(e) => {
                const id = e.target.value
                setVisitId(id)
                const hit = visits.find((v) => String(v.id) === id)
                if (hit) applyVisit(hit)
              }}
            >
              <option value="">None / draft only</option>
              {visits.map((v) => (
                <option key={v.id} value={v.id}>
                  Visit #{v.id} · {v.check_in_at || v.status || 'check-in'}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Customer-reported problem">
            <textarea
              className="input"
              rows={3}
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="What the customer reported…"
            />
          </Field>
          <Field label="Inspection notes">
            <textarea
              className="input"
              rows={3}
              value={inspectionNotes}
              onChange={(e) => setInspectionNotes(e.target.value)}
              placeholder="Existing damage / advisor notes…"
            />
          </Field>
          <Field label="Odometer">
            <input className="input" value={odometer} onChange={(e) => setOdometer(e.target.value)} />
          </Field>
          <Field label="Fuel level">
            <select className="select" value={fuel} onChange={(e) => setFuel(e.target.value)}>
              <option value="">—</option>
              <option value="E">Empty</option>
              <option value="1/4">1/4</option>
              <option value="1/2">1/2</option>
              <option value="3/4">3/4</option>
              <option value="F">Full</option>
            </select>
          </Field>
          <Field label="Priority">
            <select className="select" value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </Field>
          <Field label="Intake timestamp">
            <input
              className="input"
              type="datetime-local"
              value={intakeAt}
              onChange={(e) => setIntakeAt(e.target.value)}
            />
          </Field>
          <Field label="Expected completion">
            <input
              className="input"
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
          </Field>
          <EntitySelect
            label="Assigned worker"
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
              setWorkerLabel(hit.name || hit.label || `Worker #${hit.id}`)
            }}
          />
          <Field label="Team">
            <input
              className="input"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="Optional bay / team"
            />
          </Field>
          <Field label="Initial status">
            <select
              className="select"
              value={status}
              onChange={(e) => setStatus(e.target.value as 'draft' | 'open')}
            >
              <option value="open">Open</option>
              <option value="draft">Draft</option>
            </select>
          </Field>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Photos and full checklist live on the vehicle check-in. Link a visit above, or open{' '}
          {car_id ? <Link to={`/cars/${car_id}?tab=checkin`}>check-in</Link> : 'check-in'} after
          registering the vehicle.
        </p>
      </Panel>

      <Panel title="Labour catalogue">
        <div className="form-grid">
          {(codes.data || []).slice(0, 12).map((c) => (
            <button key={c.id} type="button" className="btn btn-ghost" onClick={() => addLabour(c)}>
              {c.code} — {c.description}
            </button>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => addLabour()}>
            Custom labour
          </button>
        </div>
      </Panel>

      <Panel title="Parts from inventory">
        <Field label="Search parts">
          <input className="input" value={invQ} onChange={(e) => setInvQ(e.target.value)} />
        </Field>
        <div className="form-grid">
          {invOptions.map((i) => (
            <button key={i.id} type="button" className="btn btn-ghost" onClick={() => addPart(i)}>
              {i.part_number} {i.name} (stock {i.quantity})
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Lines">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Type</th>
                <th>Description</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Pay</th>
                <th>Tech</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((ln, idx) => (
                <tr key={idx}>
                  <td>{ln.line_type}</td>
                  <td>
                    <input
                      className="input"
                      value={ln.description}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, description: e.target.value }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      type="number"
                      value={ln.quantity}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, quantity: Number(e.target.value) }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      type="number"
                      value={ln.unit_price}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, unit_price: Number(e.target.value) }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <select
                      className="select"
                      value={ln.pay_type}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, pay_type: e.target.value }
                        setLines(next)
                      }}
                    >
                      <option value="customer">customer</option>
                      <option value="warranty">warranty</option>
                      <option value="internal">internal</option>
                    </select>
                  </td>
                  <td>
                    <input
                      className="input"
                      value={ln.assigned_technician || ''}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, assigned_technician: e.target.value }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => setLines(lines.filter((_, i) => i !== idx))}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row-actions" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={create.isPending}
            onClick={() => create.mutate('draft')}
          >
            {create.isPending && status === 'draft' ? 'Saving…' : 'Save draft'}
          </button>
          <button
            type="button"
            className="btn"
            disabled={create.isPending || !customer_name}
            onClick={() => create.mutate('open')}
          >
            {create.isPending ? 'Creating…' : 'Create job card'}
          </button>
        </div>
      </Panel>
    </div>
  )
}

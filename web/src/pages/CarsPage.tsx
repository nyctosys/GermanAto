import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import { checkDuplicate } from '../api/entities'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  PageHeader,
  Panel,
} from '../components/ui'

type Customer = {
  id: number
  code?: string
  name: string
  phone: string
  alternate_phone?: string | null
  address?: string
  customer_type?: string
  notes?: string | null
  consent_whatsapp?: boolean
  consent_sms?: boolean
  consent_call?: boolean
  vehicles?: Car[]
  vehicle_count?: number
}

type Car = {
  id: number
  code?: string
  make?: string
  model?: string
  year?: number | null
  plate_no?: string
  mileage?: string
  vin?: string
  color?: string
  chasis_no?: string
  engine_no?: string
  notes?: string | null
  customer_id?: number | null
  customer_name?: string
  customer_phone?: string
}

type GatePassRow = {
  id: number
  document_no?: string
  direction?: string
  plate_no?: string
  customer_name?: string
  purpose?: string
  passed_at?: string
}

const emptyCustomer = {
  name: '',
  phone: '',
  alternate_phone: '',
  address: '',
  customer_type: 'retail',
  notes: '',
  consent_whatsapp: false,
  consent_sms: false,
  consent_call: true,
}

const emptyCar = {
  make: '',
  model: '',
  year: '',
  plate_no: '',
  mileage: '',
  vin: '',
  color: '',
  chasis_no: '',
  engine_no: '',
  notes: '',
  customer_id: '' as string | number,
}

export function CarsPage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const [sp, setSp] = useSearchParams()
  const showGate = sp.get('gate_pass') === '1'
  const initialTab = sp.get('tab') === 'customers' ? 'customers' : 'cars'
  const [tab, setTab] = useState<'cars' | 'customers'>(initialTab)

  const [customerForm, setCustomerForm] = useState(emptyCustomer)
  const [phoneLookup, setPhoneLookup] = useState('')
  const [phoneMatches, setPhoneMatches] = useState<Customer[]>([])
  const [dupWarning, setDupWarning] = useState<string | null>(null)
  const [forceCreate, setForceCreate] = useState(false)

  const [carForm, setCarForm] = useState(emptyCar)
  const [q, setQ] = useState(sp.get('q') || '')
  const [page, setPage] = useState(1)
  const [custPage, setCustPage] = useState(1)

  const [gateForm, setGateForm] = useState({
    direction: 'in',
    plate_no: '',
    customer_name: '',
    purpose: '',
    notes: '',
  })

  useEffect(() => {
    const next = new URLSearchParams(sp)
    next.set('tab', tab)
    setSp(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only sync tab
  }, [tab])

  const customers = useQuery({
    queryKey: ['customers', custPage, q, tab],
    enabled: tab === 'customers',
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(custPage),
        per_page: '25',
      })
      if (q.trim()) params.set('q', q.trim())
      return api.get<{ customers: Customer[]; total: number; page: number }>(
        `/api/customers?${params}`,
      )
    },
  })

  const cars = useQuery({
    queryKey: ['cars', page, q, tab],
    enabled: tab === 'cars',
    queryFn: async () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: '25',
      })
      if (q.trim()) params.set('q', q.trim())
      return api.get<{ cars: Car[]; total: number; page: number }>(`/api/cars?${params}`)
    },
  })

  const customerOptions = useQuery({
    queryKey: ['customers-options'],
    queryFn: async () => {
      const data = await api.get<Customer[] | { customers: Customer[] }>(
        '/api/customers?per_page=100&page=1',
      )
      return Array.isArray(data) ? data : data.customers || []
    },
  })

  const gatePasses = useQuery({
    queryKey: ['gate-passes'],
    queryFn: async () => {
      const data = await api.get<{ gate_passes?: GatePassRow[] }>('/api/gate-passes?limit=30')
      return data.gate_passes || []
    },
    enabled: showGate,
  })

  const lookupPhone = useMutation({
    mutationFn: async (phone: string) => {
      const data = await api.get<{ results: Customer[]; duplicate: boolean; message?: string }>(
        `/api/customers/by-phone?phone=${encodeURIComponent(phone)}`,
      )
      return data
    },
    onSuccess: (data) => {
      setPhoneMatches(data.results || [])
      setDupWarning(data.duplicate ? data.message || 'Matching customer(s) found' : null)
    },
  })

  const createCustomer = useMutation({
    mutationFn: async () => {
      const dup = await checkDuplicate('customer', {
        phone: customerForm.phone,
        name: customerForm.name,
      })
      if (dup.duplicate && !forceCreate) {
        setPhoneMatches(
          (dup.matches || []).map((m) => ({
            id: m.id,
            name: m.name || '',
            phone: m.phone || '',
            code: m.code || undefined,
            address: m.address || undefined,
          })),
        )
        setDupWarning(dup.message || dup.warnings?.[0] || 'Possible duplicate')
        throw new Error(dup.message || 'Possible duplicate — select existing or force create')
      }
      return api.post<{ customer: Customer }>('/api/customers', {
        ...customerForm,
        force: forceCreate,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customers'] })
      qc.invalidateQueries({ queryKey: ['customers-options'] })
      setCustomerForm(emptyCustomer)
      setPhoneMatches([])
      setDupWarning(null)
      setForceCreate(false)
    },
  })

  const createCar = useMutation({
    mutationFn: () =>
      api.post<{ car: Car; reused?: boolean; message?: string }>('/api/cars', {
        ...carForm,
        year: carForm.year ? Number(carForm.year) : null,
        customer_id: carForm.customer_id ? Number(carForm.customer_id) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cars'] })
      setCarForm(emptyCar)
    },
  })

  const createGate = useMutation({
    mutationFn: () => api.post('/api/gate-passes', gateForm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gate-passes'] })
      setGateForm({ direction: 'in', plate_no: '', customer_name: '', purpose: '', notes: '' })
    },
  })

  const deleteCustomer = useMutation({
    mutationFn: (id: number) => api.delete(`/api/customers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customers'] }),
  })

  const deleteCar = useMutation({
    mutationFn: (id: number) => api.delete(`/api/cars/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cars'] }),
  })

  const custList = customers.data?.customers || []
  const carList = cars.data?.cars || []
  const custTotal = customers.data?.total || 0
  const carTotal = cars.data?.total || 0

  return (
    <div>
      <PageHeader title="Customers & vehicles" />

      {showGate ? (
        <Panel title="Gate passes">
          {createGate.error ? <ErrorBox error={createGate.error} /> : null}
          <FormGrid
            onSubmit={(e) => {
              e.preventDefault()
              createGate.mutate()
            }}
          >
            <Field label="Direction">
              <select
                className="select"
                value={gateForm.direction}
                onChange={(e) => setGateForm({ ...gateForm, direction: e.target.value })}
              >
                <option value="in">In</option>
                <option value="out">Out</option>
              </select>
            </Field>
            <Field label="Plate">
              <input
                className="input"
                value={gateForm.plate_no}
                onChange={(e) => setGateForm({ ...gateForm, plate_no: e.target.value })}
              />
            </Field>
            <Field label="Customer">
              <input
                className="input"
                value={gateForm.customer_name}
                onChange={(e) => setGateForm({ ...gateForm, customer_name: e.target.value })}
              />
            </Field>
            <Field label="Purpose">
              <input
                className="input"
                value={gateForm.purpose}
                onChange={(e) => setGateForm({ ...gateForm, purpose: e.target.value })}
              />
            </Field>
            <button className="btn" type="submit" disabled={createGate.isPending}>
              Create gate pass
            </button>
          </FormGrid>
          {gatePasses.isLoading ? <Loading /> : null}
          {(gatePasses.data || []).length > 0 ? (
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Dir</th>
                    <th>Plate</th>
                    <th>Customer</th>
                    <th>Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {(gatePasses.data || []).map((g) => (
                    <tr key={g.id}>
                      <td>{g.passed_at || g.document_no}</td>
                      <td>{g.direction}</td>
                      <td>{g.plate_no}</td>
                      <td>{g.customer_name}</td>
                      <td>{g.purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Panel>
      ) : null}

      <div className="tabs">
        <button
          type="button"
          className={`tab${tab === 'cars' ? ' is-active' : ''}`}
          onClick={() => setTab('cars')}
        >
          Vehicles
        </button>
        <button
          type="button"
          className={`tab${tab === 'customers' ? ' is-active' : ''}`}
          onClick={() => setTab('customers')}
        >
          Customers
        </button>
      </div>

      <Panel title="Search">
        <div className="form-grid">
          <input
            className="input"
            placeholder={
              tab === 'customers'
                ? 'Search name, phone, code…'
                : 'Search plate, VIN, make, customer…'
            }
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
              setCustPage(1)
            }}
          />
        </div>
      </Panel>

      {tab === 'customers' ? (
        <>
          <Panel title="Register customer (search phone first)">
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                if (phoneLookup.trim()) lookupPhone.mutate(phoneLookup.trim())
              }}
            >
              <Field label="Lookup phone before create">
                <input
                  className="input"
                  placeholder="03XX XXXXXXX"
                  value={phoneLookup}
                  onChange={(e) => setPhoneLookup(e.target.value)}
                />
              </Field>
              <button className="btn btn-secondary" type="submit" disabled={lookupPhone.isPending}>
                Search phone
              </button>
            </FormGrid>

            {dupWarning ? <div className="warning-box">{dupWarning}</div> : null}
            {phoneMatches.length > 0 ? (
              <div className="table-wrap" style={{ marginBottom: 12 }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>Phone</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {phoneMatches.map((m) => (
                      <tr key={m.id}>
                        <td>{m.code || m.id}</td>
                        <td>{m.name}</td>
                        <td>{m.phone}</td>
                        <td>
                          <Link className="btn btn-secondary btn-sm" to={`/customers/${m.id}`}>
                            Open existing
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {createCustomer.error ? <ErrorBox error={createCustomer.error} /> : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                createCustomer.mutate()
              }}
            >
              <Field label="Name">
                <input
                  className="input"
                  required
                  value={customerForm.name}
                  onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })}
                />
              </Field>
              <Field label="Phone">
                <input
                  className="input"
                  required
                  value={customerForm.phone}
                  onChange={(e) => setCustomerForm({ ...customerForm, phone: e.target.value })}
                />
              </Field>
              <Field label="Alternate phone">
                <input
                  className="input"
                  value={customerForm.alternate_phone}
                  onChange={(e) =>
                    setCustomerForm({ ...customerForm, alternate_phone: e.target.value })
                  }
                />
              </Field>
              <Field label="Address">
                <input
                  className="input"
                  value={customerForm.address}
                  onChange={(e) => setCustomerForm({ ...customerForm, address: e.target.value })}
                />
              </Field>
              <Field label="Customer type">
                <select
                  className="select"
                  value={customerForm.customer_type}
                  onChange={(e) =>
                    setCustomerForm({ ...customerForm, customer_type: e.target.value })
                  }
                >
                  <option value="retail">Retail</option>
                  <option value="fleet">Fleet</option>
                  <option value="insurance">Insurance</option>
                  <option value="corporate">Corporate</option>
                  <option value="walk_in">Walk-in</option>
                  <option value="other">Other</option>
                </select>
              </Field>
              <Field label="Notes">
                <input
                  className="input"
                  value={customerForm.notes}
                  onChange={(e) => setCustomerForm({ ...customerForm, notes: e.target.value })}
                />
              </Field>
              <label className="field">
                <span>
                  <input
                    type="checkbox"
                    checked={customerForm.consent_whatsapp}
                    onChange={(e) =>
                      setCustomerForm({ ...customerForm, consent_whatsapp: e.target.checked })
                    }
                  />{' '}
                  WhatsApp consent
                </span>
              </label>
              <label className="field">
                <span>
                  <input
                    type="checkbox"
                    checked={customerForm.consent_sms}
                    onChange={(e) =>
                      setCustomerForm({ ...customerForm, consent_sms: e.target.checked })
                    }
                  />{' '}
                  SMS consent
                </span>
              </label>
              <label className="field">
                <span>
                  <input
                    type="checkbox"
                    checked={customerForm.consent_call}
                    onChange={(e) =>
                      setCustomerForm({ ...customerForm, consent_call: e.target.checked })
                    }
                  />{' '}
                  Call consent
                </span>
              </label>
              <label className="field">
                <span>
                  <input
                    type="checkbox"
                    checked={forceCreate}
                    onChange={(e) => setForceCreate(e.target.checked)}
                  />{' '}
                  Force create despite duplicate warning
                </span>
              </label>
              <button className="btn" type="submit" disabled={createCustomer.isPending}>
                Create customer
              </button>
            </FormGrid>
          </Panel>

          <Panel title={`Customers (${custTotal})`}>
            {customers.isLoading ? <Loading /> : null}
            {customers.error ? <ErrorBox error={customers.error} /> : null}
            {!customers.isLoading && custList.length === 0 ? <Empty /> : null}
            {custList.length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>Phone</th>
                      <th>Type</th>
                      <th>Address</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {custList.map((c) => (
                      <tr key={c.id}>
                        <td>{c.code || c.id}</td>
                        <td>{c.name}</td>
                        <td>
                          {c.phone}
                          {c.alternate_phone ? (
                            <span className="muted"> / {c.alternate_phone}</span>
                          ) : null}
                        </td>
                        <td>{(c.customer_type || 'retail').replaceAll('_', ' ')}</td>
                        <td>{c.address}</td>
                        <td className="row-actions">
                          <Link className="btn btn-secondary btn-sm" to={`/customers/${c.id}`}>
                            Open
                          </Link>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={async () => {
                              if (await confirm({ message: 'Delete customer? Vehicles stay for history.', danger: true, confirmLabel: 'Delete' }))
                                deleteCustomer.mutate(c.id)
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
            <div className="row-actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={custPage <= 1}
                onClick={() => setCustPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <span className="muted">
                Page {custPage} · {custTotal} total
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={custPage * 25 >= custTotal}
                onClick={() => setCustPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </Panel>
        </>
      ) : (
        <>
          <Panel title="Register vehicle (intake)">
            {createCar.error ? <ErrorBox error={createCar.error} /> : null}
            {createCar.isSuccess ? (
              <p className="muted">
                {(createCar.data as { message?: string })?.message || 'Saved'}
                {(createCar.data as { reused?: boolean })?.reused
                  ? ' — existing vehicle reused (history preserved).'
                  : ''}
              </p>
            ) : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                createCar.mutate()
              }}
            >
              <Field label="Owner">
                <select
                  className="select"
                  value={String(carForm.customer_id)}
                  onChange={(e) => setCarForm({ ...carForm, customer_id: e.target.value })}
                >
                  <option value="">Select customer…</option>
                  {(customerOptions.data || []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code || c.id} · {c.name} · {c.phone}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Plate">
                <input
                  className="input"
                  value={carForm.plate_no}
                  onChange={(e) => setCarForm({ ...carForm, plate_no: e.target.value })}
                />
              </Field>
              <Field label="Make">
                <input
                  className="input"
                  value={carForm.make}
                  onChange={(e) => setCarForm({ ...carForm, make: e.target.value })}
                />
              </Field>
              <Field label="Model">
                <input
                  className="input"
                  value={carForm.model}
                  onChange={(e) => setCarForm({ ...carForm, model: e.target.value })}
                />
              </Field>
              <Field label="Year">
                <input
                  className="input"
                  type="number"
                  value={carForm.year}
                  onChange={(e) => setCarForm({ ...carForm, year: e.target.value })}
                />
              </Field>
              <Field label="VIN">
                <input
                  className="input"
                  value={carForm.vin}
                  onChange={(e) => setCarForm({ ...carForm, vin: e.target.value })}
                />
              </Field>
              <Field label="Chassis">
                <input
                  className="input"
                  value={carForm.chasis_no}
                  onChange={(e) => setCarForm({ ...carForm, chasis_no: e.target.value })}
                />
              </Field>
              <Field label="Engine no">
                <input
                  className="input"
                  value={carForm.engine_no}
                  onChange={(e) => setCarForm({ ...carForm, engine_no: e.target.value })}
                />
              </Field>
              <Field label="Mileage">
                <input
                  className="input"
                  value={carForm.mileage}
                  onChange={(e) => setCarForm({ ...carForm, mileage: e.target.value })}
                />
              </Field>
              <Field label="Color">
                <input
                  className="input"
                  value={carForm.color}
                  onChange={(e) => setCarForm({ ...carForm, color: e.target.value })}
                />
              </Field>
              <Field label="Notes">
                <input
                  className="input"
                  value={carForm.notes}
                  onChange={(e) => setCarForm({ ...carForm, notes: e.target.value })}
                />
              </Field>
              <button className="btn" type="submit" disabled={createCar.isPending}>
                Save vehicle
              </button>
            </FormGrid>
            <p className="muted" style={{ fontSize: '0.85rem' }}>
              Same plate for the same owner (or same VIN) reuses the existing record so ownership
              transfers and prior repairs stay linked.
            </p>
          </Panel>

          <Panel title={`Vehicles (${carTotal})`}>
            {cars.isLoading ? <Loading /> : null}
            {cars.error ? <ErrorBox error={cars.error} /> : null}
            {!cars.isLoading && carList.length === 0 ? <Empty /> : null}
            {carList.length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Plate</th>
                      <th>Vehicle</th>
                      <th>Owner</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {carList.map((car) => (
                      <tr key={car.id}>
                        <td>{car.code || car.id}</td>
                        <td>{car.plate_no || '—'}</td>
                        <td>
                          {car.make} {car.model}
                          {car.year ? ` (${car.year})` : ''}
                        </td>
                        <td>
                          {car.customer_id ? (
                            <Link to={`/customers/${car.customer_id}`}>
                              {car.customer_name || car.customer_id}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="row-actions">
                          <Link className="btn btn-secondary btn-sm" to={`/cars/${car.id}`}>
                            Open
                          </Link>
                          <Link
                            className="btn btn-sm"
                            to={`/repair-orders/new?car_id=${car.id}${
                              car.customer_id ? `&customer_id=${car.customer_id}` : ''
                            }`}
                          >
                            Job card
                          </Link>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={async () => {
                              if (await confirm({ message: 'Delete this vehicle?', danger: true, confirmLabel: 'Delete' })) deleteCar.mutate(car.id)
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
            <div className="row-actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <span className="muted">
                Page {page} · {carTotal} total
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page * 25 >= carTotal}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}

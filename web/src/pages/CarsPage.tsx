import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
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
  address: string
}

type Car = {
  id: number
  make: string
  model: string
  plate_no?: string
  mileage?: string
  vin?: string
  color?: string
  chasis_no?: string
  customer_id?: number | null
  customer_name?: string
}

const emptyCustomer = { name: '', phone: '', address: '' }
const emptyCar = {
  make: '',
  model: '',
  plate_no: '',
  mileage: '',
  vin: '',
  color: '',
  chasis_no: '',
  customer_id: '' as string | number,
}

export function CarsPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'cars' | 'customers'>('cars')
  const [customerForm, setCustomerForm] = useState(emptyCustomer)
  const [editingCustomer, setEditingCustomer] = useState<number | null>(null)
  const [carForm, setCarForm] = useState(emptyCar)
  const [editingCar, setEditingCar] = useState<number | null>(null)
  const [q, setQ] = useState('')

  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: () => api.get<Customer[]>('/api/customers'),
  })
  const cars = useQuery({
    queryKey: ['cars', q],
    queryFn: async () => {
      if (q.trim()) {
        const data = await api.get<{ results: Car[] }>(
          `/api/cars/search?q=${encodeURIComponent(q.trim())}`,
        )
        return data.results || []
      }
      return api.get<Car[]>('/api/cars')
    },
  })

  const saveCustomer = useMutation({
    mutationFn: async () => {
      if (editingCustomer) {
        return api.put(`/api/customers/${editingCustomer}`, customerForm)
      }
      return api.post('/api/customers', customerForm)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customers'] })
      setCustomerForm(emptyCustomer)
      setEditingCustomer(null)
    },
  })

  const deleteCustomer = useMutation({
    mutationFn: (id: number) => api.delete(`/api/customers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customers'] }),
  })

  const saveCar = useMutation({
    mutationFn: async () => {
      const body = {
        ...carForm,
        customer_id: carForm.customer_id === '' ? null : Number(carForm.customer_id),
      }
      if (editingCar) return api.put(`/api/cars/${editingCar}`, body)
      return api.post('/api/cars', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cars'] })
      setCarForm(emptyCar)
      setEditingCar(null)
    },
  })

  const deleteCar = useMutation({
    mutationFn: (id: number) => api.delete(`/api/cars/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cars'] }),
  })

  function onCustomerSubmit(e: FormEvent) {
    e.preventDefault()
    saveCustomer.mutate()
  }

  function onCarSubmit(e: FormEvent) {
    e.preventDefault()
    saveCar.mutate()
  }

  return (
    <div>
      <PageHeader title="Cars & customers" />
      <div className="tabs">
        <button
          type="button"
          className={`tab${tab === 'cars' ? ' is-active' : ''}`}
          onClick={() => setTab('cars')}
        >
          Cars
        </button>
        <button
          type="button"
          className={`tab${tab === 'customers' ? ' is-active' : ''}`}
          onClick={() => setTab('customers')}
        >
          Customers
        </button>
      </div>

      {tab === 'customers' ? (
        <>
          <Panel title={editingCustomer ? 'Edit customer' : 'Add customer'}>
            {(saveCustomer.error || deleteCustomer.error) && (
              <ErrorBox error={saveCustomer.error || deleteCustomer.error} />
            )}
            <FormGrid onSubmit={onCustomerSubmit}>
              <Field label="Name">
                <input
                  required
                  value={customerForm.name}
                  onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })}
                />
              </Field>
              <Field label="Phone">
                <input
                  required
                  value={customerForm.phone}
                  onChange={(e) => setCustomerForm({ ...customerForm, phone: e.target.value })}
                />
              </Field>
              <Field label="Address">
                <input
                  required
                  value={customerForm.address}
                  onChange={(e) => setCustomerForm({ ...customerForm, address: e.target.value })}
                />
              </Field>
              <button className="btn" type="submit" disabled={saveCustomer.isPending}>
                {editingCustomer ? 'Update' : 'Create'}
              </button>
              {editingCustomer ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setEditingCustomer(null)
                    setCustomerForm(emptyCustomer)
                  }}
                >
                  Cancel
                </button>
              ) : null}
            </FormGrid>
          </Panel>
          <Panel title="Customers">
            {customers.isLoading ? <Loading /> : null}
            {customers.error ? <ErrorBox error={customers.error} /> : null}
            {!customers.isLoading && !(customers.data || []).length ? <Empty /> : null}
            {(customers.data || []).length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Phone</th>
                      <th>Address</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {(customers.data || []).map((c) => (
                      <tr key={c.id}>
                        <td>{c.code || c.id}</td>
                        <td>{c.name}</td>
                        <td>{c.phone}</td>
                        <td>{c.address}</td>
                        <td className="row-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setEditingCustomer(c.id)
                              setCustomerForm({
                                name: c.name,
                                phone: c.phone,
                                address: c.address,
                              })
                            }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => {
                              if (confirm('Delete this customer?')) deleteCustomer.mutate(c.id)
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
        </>
      ) : (
        <>
          <Panel title={editingCar ? 'Edit car' : 'Add car'}>
            {(saveCar.error || deleteCar.error) && (
              <ErrorBox error={saveCar.error || deleteCar.error} />
            )}
            <FormGrid onSubmit={onCarSubmit}>
              <Field label="Make">
                <input
                  required
                  value={carForm.make}
                  onChange={(e) => setCarForm({ ...carForm, make: e.target.value })}
                />
              </Field>
              <Field label="Model">
                <input
                  required
                  value={carForm.model}
                  onChange={(e) => setCarForm({ ...carForm, model: e.target.value })}
                />
              </Field>
              <Field label="Plate">
                <input
                  value={carForm.plate_no}
                  onChange={(e) => setCarForm({ ...carForm, plate_no: e.target.value })}
                />
              </Field>
              <Field label="Mileage">
                <input
                  value={carForm.mileage}
                  onChange={(e) => setCarForm({ ...carForm, mileage: e.target.value })}
                />
              </Field>
              <Field label="VIN">
                <input
                  value={carForm.vin}
                  onChange={(e) => setCarForm({ ...carForm, vin: e.target.value })}
                />
              </Field>
              <Field label="Color">
                <input
                  value={carForm.color}
                  onChange={(e) => setCarForm({ ...carForm, color: e.target.value })}
                />
              </Field>
              <Field label="Chassis">
                <input
                  value={carForm.chasis_no}
                  onChange={(e) => setCarForm({ ...carForm, chasis_no: e.target.value })}
                />
              </Field>
              <Field label="Customer">
                <select
                  value={carForm.customer_id}
                  onChange={(e) => setCarForm({ ...carForm, customer_id: e.target.value })}
                >
                  <option value="">Unassigned</option>
                  {(customers.data || []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <button className="btn" type="submit" disabled={saveCar.isPending}>
                {editingCar ? 'Update' : 'Create'}
              </button>
            </FormGrid>
          </Panel>
          <Panel
            title="Cars"
            actions={
              <input
                className="input"
                placeholder="Search plate / VIN / customer"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                style={{ width: 200 }}
              />
            }
          >
            {cars.isLoading ? <Loading /> : null}
            {cars.error ? <ErrorBox error={cars.error} /> : null}
            {!cars.isLoading && !(cars.data || []).length ? <Empty /> : null}
            {(cars.data || []).length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Make</th>
                      <th>Model</th>
                      <th>Plate</th>
                      <th>Customer</th>
                      <th>VIN</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {(cars.data || []).map((c) => (
                      <tr key={c.id}>
                        <td>{c.make}</td>
                        <td>{c.model}</td>
                        <td>{c.plate_no}</td>
                        <td>{c.customer_name || c.customer_id || '—'}</td>
                        <td>{c.vin || '—'}</td>
                        <td className="row-actions">
                          <Link className="btn btn-secondary btn-sm" to={`/cars/${c.id}`}>
                            History
                          </Link>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setEditingCar(c.id)
                              setCarForm({
                                make: c.make,
                                model: c.model,
                                plate_no: c.plate_no || '',
                                mileage: c.mileage || '',
                                vin: c.vin || '',
                                color: c.color || '',
                                chasis_no: c.chasis_no || '',
                                customer_id: c.customer_id || '',
                              })
                            }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => {
                              if (confirm('Delete this car?')) deleteCar.mutate(c.id)
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
        </>
      )}
    </div>
  )
}

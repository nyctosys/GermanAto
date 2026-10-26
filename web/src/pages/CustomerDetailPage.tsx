import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
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

type Customer = {
  id: number
  code?: string
  name?: string
  phone?: string
  alternate_phone?: string | null
  address?: string | null
  customer_type?: string
  notes?: string | null
  consent_whatsapp?: boolean
  consent_sms?: boolean
  consent_call?: boolean
  version?: number
}

type Vehicle = {
  id: number
  code?: string
  make?: string
  model?: string
  year?: number | null
  plate_no?: string
  vin?: string
  mileage?: string
  color?: string
  chasis_no?: string
  engine_no?: string
  notes?: string | null
}

type Activity = {
  receivable_total?: number
  open_invoice_count?: number
  open_invoices?: Array<{ id: number; document_no?: string; owed?: number; status?: string }>
  recent_invoices?: Array<{ id: number; document_no?: string; net_total?: number; status?: string; created_at?: string }>
  recent_estimates?: Array<{ id: number; document_no?: string; net_total?: number; status?: string; created_at?: string }>
  recent_repairs?: Array<{
    id: number
    document_no?: string
    customer_reg_no?: string
    current_status?: string
    created_at?: string
  }>
  counts?: { invoices?: number; estimates?: number; repairs?: number; vehicles?: number }
}

type Bundle = {
  customer: Customer
  vehicles?: Vehicle[]
  activity?: Activity
}

const emptyVehicle = {
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
}

export function CustomerDetailPage() {
  const { id } = useParams()
  const customerId = Number(id)
  const qc = useQueryClient()
  const [vehicleForm, setVehicleForm] = useState(emptyVehicle)
  const [edit, setEdit] = useState<Partial<Customer> | null>(null)

  const q = useQuery({
    queryKey: ['customer', customerId],
    enabled: Number.isFinite(customerId) && customerId > 0,
    queryFn: () => api.get<Bundle>(`/api/customers/${customerId}`),
  })

  const saveCustomer = useMutation({
    mutationFn: () =>
      api.put(`/api/customers/${customerId}`, {
        ...edit,
        version: q.data?.customer.version,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customer', customerId] })
      setEdit(null)
    },
  })

  const addVehicle = useMutation({
    mutationFn: () =>
      api.post<{ car: Vehicle; reused?: boolean; message?: string }>('/api/cars', {
        customer_id: customerId,
        make: vehicleForm.make || null,
        model: vehicleForm.model || null,
        year: vehicleForm.year ? Number(vehicleForm.year) : null,
        plate_no: vehicleForm.plate_no || null,
        mileage: vehicleForm.mileage || null,
        vin: vehicleForm.vin || null,
        color: vehicleForm.color || null,
        chasis_no: vehicleForm.chasis_no || null,
        engine_no: vehicleForm.engine_no || null,
        notes: vehicleForm.notes || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['customer', customerId] })
      setVehicleForm(emptyVehicle)
    },
  })

  const c = q.data?.customer
  const activity = q.data?.activity
  const vehicles = q.data?.vehicles || []

  function startEdit() {
    if (!c) return
    setEdit({
      name: c.name || '',
      phone: c.phone || '',
      alternate_phone: c.alternate_phone || '',
      address: c.address || '',
      customer_type: c.customer_type || 'retail',
      notes: c.notes || '',
      consent_whatsapp: !!c.consent_whatsapp,
      consent_sms: !!c.consent_sms,
      consent_call: c.consent_call !== false,
    })
  }

  return (
    <div>
      <PageHeader
        title={c ? `${c.code || `CN-${c.id}`} · ${c.name || 'Customer'}` : 'Customer'}
        actions={
          <div className="row-actions">
            <Link className="btn btn-secondary" to="/cars?tab=customers">
              Back to list
            </Link>
            {c && !edit ? (
              <button type="button" className="btn btn-secondary" onClick={startEdit}>
                Edit
              </button>
            ) : null}
            <Link className="btn" to={`/repair-orders/new?customer_id=${customerId}`}>
              New job card
            </Link>
          </div>
        }
      />

      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}

      {c ? (
        <>
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Outstanding balance</div>
              <div className="value">
                <Money value={activity?.receivable_total || 0} />
              </div>
            </div>
            <div className="stat">
              <div className="label">Vehicles</div>
              <div className="value">{activity?.counts?.vehicles ?? vehicles.length}</div>
            </div>
            <div className="stat">
              <div className="label">Repairs</div>
              <div className="value">{activity?.counts?.repairs || 0}</div>
            </div>
            <div className="stat">
              <div className="label">Estimates / invoices</div>
              <div className="value">
                {(activity?.counts?.estimates || 0) + (activity?.counts?.invoices || 0)}
              </div>
            </div>
          </div>

          {edit ? (
            <Panel title="Edit customer">
              {saveCustomer.error ? <ErrorBox error={saveCustomer.error} /> : null}
              <FormGrid
                onSubmit={(e: FormEvent) => {
                  e.preventDefault()
                  saveCustomer.mutate()
                }}
              >
                <Field label="Name">
                  <input
                    className="input"
                    required
                    value={String(edit.name || '')}
                    onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                  />
                </Field>
                <Field label="Phone">
                  <input
                    className="input"
                    required
                    value={String(edit.phone || '')}
                    onChange={(e) => setEdit({ ...edit, phone: e.target.value })}
                  />
                </Field>
                <Field label="Alternate phone">
                  <input
                    className="input"
                    value={String(edit.alternate_phone || '')}
                    onChange={(e) => setEdit({ ...edit, alternate_phone: e.target.value })}
                  />
                </Field>
                <Field label="Address">
                  <input
                    className="input"
                    value={String(edit.address || '')}
                    onChange={(e) => setEdit({ ...edit, address: e.target.value })}
                  />
                </Field>
                <Field label="Customer type">
                  <select
                    className="select"
                    value={String(edit.customer_type || 'retail')}
                    onChange={(e) => setEdit({ ...edit, customer_type: e.target.value })}
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
                  <textarea
                    className="input"
                    rows={2}
                    value={String(edit.notes || '')}
                    onChange={(e) => setEdit({ ...edit, notes: e.target.value })}
                  />
                </Field>
                <label className="field">
                  <span>
                    <input
                      type="checkbox"
                      checked={!!edit.consent_whatsapp}
                      onChange={(e) => setEdit({ ...edit, consent_whatsapp: e.target.checked })}
                    />{' '}
                    WhatsApp consent
                  </span>
                </label>
                <label className="field">
                  <span>
                    <input
                      type="checkbox"
                      checked={!!edit.consent_sms}
                      onChange={(e) => setEdit({ ...edit, consent_sms: e.target.checked })}
                    />{' '}
                    SMS consent
                  </span>
                </label>
                <label className="field">
                  <span>
                    <input
                      type="checkbox"
                      checked={edit.consent_call !== false}
                      onChange={(e) => setEdit({ ...edit, consent_call: e.target.checked })}
                    />{' '}
                    Call consent
                  </span>
                </label>
                <button className="btn" type="submit" disabled={saveCustomer.isPending}>
                  Save
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setEdit(null)}>
                  Cancel
                </button>
              </FormGrid>
            </Panel>
          ) : (
            <Panel title="Profile">
              <div className="form-grid">
                <div>
                  <div className="muted">Phone</div>
                  <strong>{c.phone || '—'}</strong>
                </div>
                <div>
                  <div className="muted">Alternate</div>
                  <strong>{c.alternate_phone || '—'}</strong>
                </div>
                <div>
                  <div className="muted">Type</div>
                  <strong>{(c.customer_type || 'retail').replaceAll('_', ' ')}</strong>
                </div>
                <div>
                  <div className="muted">Address</div>
                  <strong>{c.address || '—'}</strong>
                </div>
                <div>
                  <div className="muted">Consent</div>
                  <strong>
                    {[
                      c.consent_whatsapp ? 'WhatsApp' : null,
                      c.consent_sms ? 'SMS' : null,
                      c.consent_call !== false ? 'Call' : null,
                    ]
                      .filter(Boolean)
                      .join(' · ') || 'None'}
                  </strong>
                </div>
                {c.notes ? (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <div className="muted">Notes</div>
                    <p style={{ margin: 0 }}>{c.notes}</p>
                  </div>
                ) : null}
              </div>
            </Panel>
          )}

          <Panel title="Vehicles">
            {vehicles.length === 0 ? <Empty>No vehicles yet</Empty> : null}
            {vehicles.length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Plate</th>
                      <th>Make / model</th>
                      <th>Year</th>
                      <th>VIN</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {vehicles.map((v) => (
                      <tr key={v.id}>
                        <td>{v.code || v.id}</td>
                        <td>{v.plate_no || '—'}</td>
                        <td>
                          {v.make} {v.model}
                        </td>
                        <td>{v.year || '—'}</td>
                        <td>{v.vin || '—'}</td>
                        <td className="row-actions">
                          <Link className="btn btn-secondary btn-sm" to={`/cars/${v.id}`}>
                            Open
                          </Link>
                          <Link
                            className="btn btn-sm"
                            to={`/repair-orders/new?car_id=${v.id}&customer_id=${customerId}`}
                          >
                            Job card
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            <h3 style={{ fontSize: '0.95rem', marginTop: 16 }}>Quick register vehicle</h3>
            {addVehicle.error ? <ErrorBox error={addVehicle.error} /> : null}
            {addVehicle.isSuccess ? (
              <p className="muted">
                {(addVehicle.data as { message?: string })?.message || 'Vehicle saved'}
              </p>
            ) : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                addVehicle.mutate()
              }}
            >
              <Field label="Plate">
                <input
                  className="input"
                  value={vehicleForm.plate_no}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, plate_no: e.target.value })}
                />
              </Field>
              <Field label="Make">
                <input
                  className="input"
                  value={vehicleForm.make}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, make: e.target.value })}
                />
              </Field>
              <Field label="Model">
                <input
                  className="input"
                  value={vehicleForm.model}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, model: e.target.value })}
                />
              </Field>
              <Field label="Year">
                <input
                  className="input"
                  type="number"
                  value={vehicleForm.year}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, year: e.target.value })}
                />
              </Field>
              <Field label="VIN">
                <input
                  className="input"
                  value={vehicleForm.vin}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, vin: e.target.value })}
                />
              </Field>
              <Field label="Mileage">
                <input
                  className="input"
                  value={vehicleForm.mileage}
                  onChange={(e) => setVehicleForm({ ...vehicleForm, mileage: e.target.value })}
                />
              </Field>
              <button className="btn" type="submit" disabled={addVehicle.isPending}>
                Register vehicle
              </button>
            </FormGrid>
            <p className="muted" style={{ fontSize: '0.85rem' }}>
              Matching plate/VIN reuses the existing vehicle so ownership and repair history stay
              intact.
            </p>
          </Panel>

          <div className="dash-panels">
            <Panel title="Open balances">
              {(activity?.open_invoices || []).length === 0 ? (
                <Empty>No outstanding invoices</Empty>
              ) : (
                <ul className="dash-list">
                  {(activity?.open_invoices || []).map((inv) => (
                    <li key={inv.id}>
                      <Link className="dash-list__row" to="/invoices?status=unpaid">
                        <span className="dash-list__main">
                          <span className="dash-list__primary">
                            {inv.document_no || `Invoice #${inv.id}`}
                          </span>
                          <span className="dash-list__secondary">{inv.status}</span>
                        </span>
                        <span className="dash-list__amount">
                          <Money value={inv.owed || 0} />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Previous repairs">
              {(activity?.recent_repairs || []).length === 0 ? (
                <Empty>No repairs</Empty>
              ) : (
                <ul className="dash-list">
                  {(activity?.recent_repairs || []).map((ro) => (
                    <li key={ro.id}>
                      <Link className="dash-list__row" to="/repair-orders">
                        <span className="dash-list__main">
                          <span className="dash-list__primary">
                            {ro.document_no || `RO #${ro.id}`} · {ro.customer_reg_no || ''}
                          </span>
                          <span className="dash-list__secondary">
                            {ro.current_status} · {ro.created_at || ''}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Estimates">
              {(activity?.recent_estimates || []).length === 0 ? (
                <Empty>No estimates</Empty>
              ) : (
                <ul className="dash-list">
                  {(activity?.recent_estimates || []).map((qt) => (
                    <li key={qt.id}>
                      <Link className="dash-list__row" to="/quotes/pending">
                        <span className="dash-list__main">
                          <span className="dash-list__primary">
                            {qt.document_no || `Quote #${qt.id}`}
                          </span>
                          <span className="dash-list__secondary">
                            {qt.status} · {qt.created_at || ''}
                          </span>
                        </span>
                        <span className="dash-list__amount">
                          <Money value={qt.net_total || 0} />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Invoices">
              {(activity?.recent_invoices || []).length === 0 ? (
                <Empty>No invoices</Empty>
              ) : (
                <ul className="dash-list">
                  {(activity?.recent_invoices || []).map((inv) => (
                    <li key={inv.id}>
                      <Link className="dash-list__row" to="/invoices">
                        <span className="dash-list__main">
                          <span className="dash-list__primary">
                            {inv.document_no || `Invoice #${inv.id}`}
                          </span>
                          <span className="dash-list__secondary">
                            {inv.status} · {inv.created_at || ''}
                          </span>
                        </span>
                        <span className="dash-list__amount">
                          <Money value={inv.net_total || 0} />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      ) : null}
    </div>
  )
}

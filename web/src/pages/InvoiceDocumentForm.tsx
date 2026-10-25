import { useQuery } from '@tanstack/react-query'
import { useMemo, type FormEvent } from 'react'
import { api } from '../api/client'
import { Field, Money, Panel } from '../components/ui'
import {
  calcNet,
  type InvoiceFormState,
  type LabourLine,
  type LineItem,
} from './invoiceTypes'

type Customer = { id: number; name: string; phone: string; address: string }
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
}
type InvItem = {
  id: number
  name: string
  manufacturer_part_number?: string
  price?: number
}

export function InvoiceDocumentForm({
  title,
  form,
  setForm,
  onSubmit,
  busy,
  showAdvance = true,
  submitLabel = 'Save',
}: {
  title: string
  form: InvoiceFormState
  setForm: (next: InvoiceFormState) => void
  onSubmit: (e: FormEvent) => void
  busy?: boolean
  showAdvance?: boolean
  submitLabel?: string
}) {
  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: () => api.get<Customer[]>('/api/customers'),
  })
  const cars = useQuery({
    queryKey: ['cars'],
    queryFn: () => api.get<Car[]>('/api/cars'),
  })
  const inventory = useQuery({
    queryKey: ['inventory-all'],
    queryFn: async () => {
      const data = await api.get<{ items?: InvItem[] } | InvItem[]>(
        '/api/inventory?per_page=500',
      )
      return Array.isArray(data) ? data : data.items || []
    },
  })

  const net = useMemo(() => calcNet(form), [form])
  const tax = form.include_tax ? net * 0.17 : 0
  const balance = net + tax - Number(form.discount) - Number(form.advance)

  function updateItem(idx: number, patch: Partial<LineItem>) {
    const items = form.items.map((it, i) => (i === idx ? { ...it, ...patch } : it))
    setForm({ ...form, items })
  }

  function updateLabour(idx: number, patch: Partial<LabourLine>) {
    const labours = form.labours.map((it, i) => (i === idx ? { ...it, ...patch } : it))
    setForm({ ...form, labours })
  }

  function pickCustomer(id: string) {
    const c = (customers.data || []).find((x) => x.id === Number(id))
    if (!c) {
      setForm({ ...form, customer_id: null })
      return
    }
    setForm({
      ...form,
      customer_id: c.id,
      customer_name: c.name,
      customer_phone: c.phone,
      customer_address: c.address,
    })
  }

  function pickCar(id: string) {
    const c = (cars.data || []).find((x) => x.id === Number(id))
    if (!c) {
      setForm({ ...form, car_id: null })
      return
    }
    setForm({
      ...form,
      car_id: c.id,
      customer_reg_no: c.plate_no || '',
      customer_made: `${c.make} ${c.model}`.trim(),
      customer_mileage: c.mileage || '',
      customer_vin: c.vin || '',
      customer_color: c.color || '',
      customer_chasis: c.chasis_no || '',
      customer_id: c.customer_id || form.customer_id,
    })
  }

  return (
    <form onSubmit={onSubmit} className="stack">
      <Panel title={title}>
        <div className="form-grid">
          <Field label="Customer">
            <select
              value={form.customer_id || ''}
              onChange={(e) => pickCustomer(e.target.value)}
            >
              <option value="">Select / type below</option>
              {(customers.data || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Car">
            <select value={form.car_id || ''} onChange={(e) => pickCar(e.target.value)}>
              <option value="">Select / type below</option>
              {(cars.data || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.make} {c.model} {c.plate_no || ''}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Customer name">
            <input
              required
              value={form.customer_name}
              onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <input
              required
              value={form.customer_phone}
              onChange={(e) => setForm({ ...form, customer_phone: e.target.value })}
            />
          </Field>
          <Field label="Address">
            <input
              required
              value={form.customer_address}
              onChange={(e) => setForm({ ...form, customer_address: e.target.value })}
            />
          </Field>
          <Field label="Reg no">
            <input
              required
              value={form.customer_reg_no}
              onChange={(e) => setForm({ ...form, customer_reg_no: e.target.value })}
            />
          </Field>
          <Field label="Make / model">
            <input
              required
              value={form.customer_made}
              onChange={(e) => setForm({ ...form, customer_made: e.target.value })}
            />
          </Field>
          <Field label="Mileage">
            <input
              required
              value={form.customer_mileage}
              onChange={(e) => setForm({ ...form, customer_mileage: e.target.value })}
            />
          </Field>
          <Field label="VIN">
            <input
              value={form.customer_vin}
              onChange={(e) => setForm({ ...form, customer_vin: e.target.value })}
            />
          </Field>
          <Field label="Color">
            <input
              value={form.customer_color}
              onChange={(e) => setForm({ ...form, customer_color: e.target.value })}
            />
          </Field>
          <Field label="Chassis">
            <input
              value={form.customer_chasis}
              onChange={(e) => setForm({ ...form, customer_chasis: e.target.value })}
            />
          </Field>
        </div>
      </Panel>

      <Panel
        title="Parts"
        actions={
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() =>
              setForm({
                ...form,
                items: [
                  ...form.items,
                  { product_name: '', part_number: '', quantity: 1, price: 0 },
                ],
              })
            }
          >
            Add part
          </button>
        }
      >
        <div className="line-items">
          {form.items.map((item, idx) => (
            <div className="line-item" key={idx}>
              <Field label="Product">
                <input
                  list="inv-names"
                  value={item.product_name}
                  onChange={(e) => {
                    const name = e.target.value
                    const match = (inventory.data || []).find((i) => i.name === name)
                    updateItem(idx, {
                      product_name: name,
                      part_number: match?.manufacturer_part_number || item.part_number,
                      price: match?.price ?? item.price,
                    })
                  }}
                />
              </Field>
              <Field label="Part #">
                <input
                  value={item.part_number}
                  onChange={(e) => updateItem(idx, { part_number: e.target.value })}
                />
              </Field>
              <Field label="Qty">
                <input
                  type="number"
                  min={1}
                  value={item.quantity}
                  onChange={(e) => updateItem(idx, { quantity: Number(e.target.value) })}
                />
              </Field>
              <Field label="Price">
                <input
                  type="number"
                  step="0.01"
                  value={item.price}
                  onChange={(e) => updateItem(idx, { price: Number(e.target.value) })}
                />
              </Field>
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() =>
                  setForm({ ...form, items: form.items.filter((_, i) => i !== idx) })
                }
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <datalist id="inv-names">
          {(inventory.data || []).map((i) => (
            <option key={i.id} value={i.name} />
          ))}
        </datalist>
      </Panel>

      <Panel
        title="Labour"
        actions={
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() =>
              setForm({
                ...form,
                labours: [...form.labours, { description: '', price: 0 }],
              })
            }
          >
            Add labour
          </button>
        }
      >
        <div className="line-items">
          {form.labours.map((lab, idx) => (
            <div className="line-item" key={idx}>
              <Field label="Description">
                <input
                  value={lab.description}
                  onChange={(e) => updateLabour(idx, { description: e.target.value })}
                />
              </Field>
              <Field label="Price">
                <input
                  type="number"
                  step="0.01"
                  value={lab.price}
                  onChange={(e) => updateLabour(idx, { price: Number(e.target.value) })}
                />
              </Field>
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() =>
                  setForm({
                    ...form,
                    labours: form.labours.filter((_, i) => i !== idx),
                  })
                }
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Totals">
        <div className="form-grid">
          {showAdvance ? (
            <Field label="Advance">
              <input
                type="number"
                step="0.01"
                value={form.advance}
                onChange={(e) => setForm({ ...form, advance: Number(e.target.value) })}
              />
            </Field>
          ) : null}
          <Field label="Discount">
            <input
              type="number"
              step="0.01"
              value={form.discount}
              onChange={(e) => setForm({ ...form, discount: Number(e.target.value) })}
            />
          </Field>
          <Field label="Include 17% tax">
            <select
              value={form.include_tax ? '1' : '0'}
              onChange={(e) => setForm({ ...form, include_tax: e.target.value === '1' })}
            >
              <option value="0">No</option>
              <option value="1">Yes</option>
            </select>
          </Field>
        </div>
        <div className="totals">
          <span>
            Net: <Money value={net} />
          </span>
          {form.include_tax ? (
            <span>
              Tax: <Money value={tax} />
            </span>
          ) : null}
          <span>
            Balance: <Money value={balance} />
          </span>
        </div>
        <div style={{ marginTop: 12 }}>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? 'Saving…' : submitLabel}
          </button>
        </div>
      </Panel>
    </form>
  )
}

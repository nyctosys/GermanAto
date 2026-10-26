import { useMemo, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { getCustomerBundle, type EntityHit } from '../api/entities'
import { EntitySelect } from '../components/EntitySelect'
import { Field, Money, Panel } from '../components/ui'
import {
  calcDurationHours,
  calcNet,
  missingParts,
  type InvoiceFormState,
  type LabourLine,
  type LineItem,
} from './invoiceTypes'

export function InvoiceDocumentForm({
  title,
  form,
  setForm,
  onSubmit,
  busy,
  showAdvance = true,
  showEstimateMeta = false,
  requiredAdvance,
  submitLabel = 'Save',
  cancelTo = '/invoices',
  readOnly = false,
  footerNote,
}: {
  title: string
  form: InvoiceFormState
  setForm: (next: InvoiceFormState) => void
  onSubmit: (e: FormEvent) => void
  busy?: boolean
  showAdvance?: boolean
  showEstimateMeta?: boolean
  requiredAdvance?: number | null
  submitLabel?: string
  cancelTo?: string
  readOnly?: boolean
  footerNote?: ReactNode
}) {
  const net = useMemo(() => calcNet(form), [form])
  const tax = form.include_tax ? net * 0.17 : 0
  const finalEst = net + tax - Number(form.discount)
  const balance = finalEst - Number(form.advance)
  const gaps = useMemo(() => missingParts(form), [form])
  const duration = useMemo(
    () => form.expected_duration_hours ?? calcDurationHours(form),
    [form],
  )

  function updateItem(idx: number, patch: Partial<LineItem>) {
    const items = form.items.map((it, i) => (i === idx ? { ...it, ...patch } : it))
    setForm({ ...form, items })
  }

  function updateLabour(idx: number, patch: Partial<LabourLine>) {
    const labours = form.labours.map((it, i) => (i === idx ? { ...it, ...patch } : it))
    setForm({ ...form, labours })
  }

  async function pickCustomer(hit: EntityHit | null) {
    if (!hit) {
      setForm({ ...form, customer_id: null })
      return
    }
    const bundle = await getCustomerBundle(hit.id)
    const c = bundle.customer
    setForm({
      ...form,
      customer_id: c.id,
      customer_name: c.name || '',
      customer_phone: c.phone || '',
      customer_address: c.address || '',
      car_id: null,
      customer_reg_no: '',
      customer_made: '',
      customer_vin: '',
      customer_color: '',
      customer_chasis: '',
    })
  }

  function pickCar(hit: EntityHit | null) {
    if (!hit) {
      setForm({ ...form, car_id: null })
      return
    }
    setForm({
      ...form,
      car_id: hit.id,
      customer_reg_no: hit.plate_no || '',
      customer_made: `${hit.make || ''} ${hit.model || ''}`.trim(),
      customer_mileage: hit.mileage || '',
      customer_vin: hit.vin || '',
      customer_color: hit.color || '',
      customer_chasis: hit.chasis_no || '',
      customer_id: hit.customer_id || form.customer_id,
      customer_name: hit.customer_name || form.customer_name,
      customer_phone: hit.customer_phone || form.customer_phone,
      customer_address: hit.customer_address || form.customer_address,
    })
  }

  function pickInventory(idx: number, hit: EntityHit | null) {
    if (!hit) return
    updateItem(idx, {
      product_name: hit.name || '',
      part_number: hit.part_number || hit.code || '',
      price: Number(hit.price || 0),
      inventory_id: hit.id,
      available: hit.available ?? null,
    })
  }

  function pickLabour(idx: number, hit: EntityHit | null) {
    if (!hit) {
      updateLabour(idx, { labour_code_id: null })
      return
    }
    updateLabour(idx, {
      description: hit.description || hit.name || hit.label || '',
      price: Number(hit.rate ?? hit.price ?? 0),
      labour_code_id: hit.id,
      std_hours: Number(hit.std_hours ?? hit.standard_hours ?? 0) || null,
    })
  }

  return (
    <form onSubmit={onSubmit} className="stack">
      <fieldset
        disabled={readOnly}
        style={{ border: 0, margin: 0, padding: 0, minInlineSize: 0 }}
      >
      <Panel title={title}>
        <div className="form-grid">
          <EntitySelect
            label="Customer"
            type="customer"
            valueId={form.customer_id}
            displayValue={
              form.customer_name
                ? `${form.customer_name} · ${form.customer_phone || ''}`.trim()
                : ''
            }
            onSelect={(hit) => {
              void pickCustomer(hit)
            }}
          />
          <EntitySelect
            label="Vehicle"
            type="car"
            valueId={form.car_id}
            customerId={form.customer_id}
            displayValue={
              form.customer_reg_no || form.customer_made
                ? `${form.customer_reg_no} · ${form.customer_made}`.trim()
                : ''
            }
            onSelect={pickCar}
          />
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
            <div className="line-item" key={idx} style={{ gridTemplateColumns: '2fr 1fr 80px 100px auto' }}>
              <EntitySelect
                label="Product"
                type="inventory"
                displayValue={item.product_name}
                placeholder="Search inventory…"
                onSelect={(hit) => {
                  if (hit) pickInventory(idx, hit)
                  else updateItem(idx, { product_name: '' })
                }}
              />
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
            <div className="line-item" key={idx} style={{ gridTemplateColumns: '2fr 100px 100px auto' }}>
              <EntitySelect
                label="Labour / task"
                type="labour_code"
                valueId={lab.labour_code_id || null}
                displayValue={lab.description}
                placeholder="Search labour codes…"
                onSelect={(hit) => pickLabour(idx, hit)}
              />
              <Field label="Hours">
                <input
                  type="number"
                  step="0.1"
                  value={lab.std_hours ?? ''}
                  onChange={(e) =>
                    updateLabour(idx, { std_hours: e.target.value ? Number(e.target.value) : null })
                  }
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

      {gaps.length > 0 ? (
        <Panel title="Missing parts (stock check)">
          <ul>
            {gaps.map((g, i) => (
              <li key={i}>
                {g.product_name} · need {g.quantity}, available {g.available ?? 0}, missing {g.missing}
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      {showEstimateMeta ? (
        <Panel title="Schedule">
          <div className="form-grid">
            <Field label="Expected duration (hours)">
              <input
                type="number"
                step="0.1"
                value={form.expected_duration_hours ?? duration}
                onChange={(e) =>
                  setForm({
                    ...form,
                    expected_duration_hours: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </Field>
            <Field label="Expected completion">
              <input
                type="datetime-local"
                value={form.expected_completion_at || ''}
                onChange={(e) => setForm({ ...form, expected_completion_at: e.target.value })}
              />
            </Field>
          </div>
        </Panel>
      ) : null}

      <Panel title="Totals">
        <div className="form-grid">
          {showAdvance ? (
            <Field label="Advance (invoice only)">
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
            Subtotal: <Money value={net} />
          </span>
          {form.include_tax ? (
            <span>
              Tax: <Money value={tax} />
            </span>
          ) : null}
          <span>
            Final estimate: <Money value={finalEst} />
          </span>
          {requiredAdvance != null ? (
            <span>
              Required advance: <Money value={requiredAdvance} />
            </span>
          ) : null}
          {showAdvance ? (
            <span>
              Balance: <Money value={balance} />
            </span>
          ) : (
            <span className="muted">Advances are liabilities (deposits), not revenue</span>
          )}
        </div>
      </Panel>
      </fieldset>
      {footerNote ? <div style={{ marginTop: 12 }}>{footerNote}</div> : null}
      <div className="row-actions" style={{ marginTop: 12, gap: 8 }}>
        {!readOnly ? (
          <button className="btn" type="submit" disabled={busy}>
            {busy ? 'Saving…' : submitLabel}
          </button>
        ) : null}
        <Link className="btn btn-secondary" to={cancelTo}>
          {readOnly ? 'Back to invoices' : 'Cancel'}
        </Link>
      </div>
    </form>
  )
}

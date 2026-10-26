import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
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

type PoRow = {
  id?: number
  item_name?: string
  description?: string
  quantity?: number
  qty_received?: number
  qty_remaining?: number
  rate?: number
  amount?: number
  status?: string
  invoice_no?: string
  inventory_id?: number | null
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export function VendorDetailPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [ledgerForm, setLedgerForm] = useState(() => ({
    amount: 0,
    description: '',
    entry_type: 'debit',
    date: todayIso(),
  }))
  const [poForm, setPoForm] = useState(() => ({
    item_name: '',
    invoice_no: '',
    quantity: 1,
    rate: 0,
    inventory_id: '',
    status: 'draft',
    date: todayIso(),
  }))
  const [receiveQty, setReceiveQty] = useState<Record<number, number>>({})

  const vendor = useQuery({
    queryKey: ['vendor', id],
    enabled: !!id,
    queryFn: () => api.get<Record<string, unknown>>(`/api/vendors/${id}`),
  })

  const ledger = useQuery({
    queryKey: ['vendor-ledger', id],
    enabled: !!id,
    queryFn: async () => {
      const data = await api.get<{ entries?: Record<string, unknown>[] } | Record<string, unknown>[]>(
        `/api/vendors/${id}/ledger`,
      )
      return Array.isArray(data) ? data : data.entries || []
    },
  })

  const pos = useQuery({
    queryKey: ['vendor-pos', id],
    enabled: !!id,
    queryFn: async () => {
      const data = await api.get<
        { purchase_orders?: PoRow[] } | PoRow[]
      >(`/api/vendors/${id}/purchase-orders`)
      return Array.isArray(data) ? data : data.purchase_orders || []
    },
  })

  const addLedger = useMutation({
    mutationFn: () =>
      api.post('/api/ledger/add', {
        vendor_id: Number(id),
        ...ledgerForm,
        amount: Number(ledgerForm.amount),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendor-ledger', id] })
      setLedgerForm({
        amount: 0,
        description: '',
        entry_type: 'debit',
        date: todayIso(),
      })
    },
  })

  const addPo = useMutation({
    mutationFn: () =>
      api.post('/api/purchase-orders/add', {
        vendor_id: Number(id),
        item_name: poForm.item_name,
        invoice_no: poForm.invoice_no || undefined,
        quantity: Number(poForm.quantity),
        rate: Number(poForm.rate),
        date: poForm.date,
        status: poForm.status,
        inventory_id: poForm.inventory_id ? Number(poForm.inventory_id) : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendor-pos', id] })
      setPoForm({
        item_name: '',
        invoice_no: '',
        quantity: 1,
        rate: 0,
        inventory_id: '',
        status: 'draft',
        date: todayIso(),
      })
    },
  })

  const orderPo = useMutation({
    mutationFn: (poId: number) =>
      api.put(`/api/purchase-orders/${poId}/status`, { status: 'ordered' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendor-pos', id] }),
  })

  const receivePo = useMutation({
    mutationFn: async ({ po, qty }: { po: PoRow; qty: number }) => {
      const receipt_attachment_path = window.prompt(
        'Supplier receipt path (required). Upload via attachments or paste stored path:',
        po.id ? `uploads/po-${po.id}-receipt.pdf` : '',
      )
      if (!receipt_attachment_path) throw new Error('Receipt required for GRN')
      return api.post(`/api/purchase-orders/${po.id}/receive`, {
        quantity: qty,
        unit_cost: po.rate,
        inventory_id: po.inventory_id,
        receipt_attachment_path,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendor-pos', id] })
      qc.invalidateQueries({ queryKey: ['vendor-ledger', id] })
      qc.invalidateQueries({ queryKey: ['inventory'] })
    },
  })

  const closePo = useMutation({
    mutationFn: (poId: number) =>
      api.put(`/api/purchase-orders/${poId}/status`, { status: 'closed' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendor-pos', id] }),
  })

  if (vendor.isLoading) return <Loading />
  if (vendor.error) return <ErrorBox error={vendor.error} />

  const v = vendor.data || {}

  return (
    <div>
      <PageHeader
        title={String(v.name || `Vendor #${id}`)}
        actions={
          <Link className="btn btn-secondary" to="/vendors">
            Back
          </Link>
        }
      />
      <Panel title="Details">
        <p>
          {String(v.company_name || '')} · {String(v.phone || '')} ·{' '}
          {String(v.email || '')}
        </p>
        <p className="muted">{String(v.address || '')}</p>
      </Panel>

      <Panel title="Add ledger entry">
        {addLedger.error ? <ErrorBox error={addLedger.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addLedger.mutate()
          }}
        >
          <Field label="Date">
            <input
              type="date"
              value={ledgerForm.date}
              onChange={(e) => setLedgerForm({ ...ledgerForm, date: e.target.value })}
            />
          </Field>
          <Field label="Type">
            <select
              value={ledgerForm.entry_type}
              onChange={(e) => setLedgerForm({ ...ledgerForm, entry_type: e.target.value })}
            >
              <option value="debit">Debit</option>
              <option value="credit">Credit</option>
            </select>
          </Field>
          <Field label="Amount">
            <input
              type="number"
              step="0.01"
              value={ledgerForm.amount}
              onChange={(e) =>
                setLedgerForm({ ...ledgerForm, amount: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Description">
            <input
              value={ledgerForm.description}
              onChange={(e) =>
                setLedgerForm({ ...ledgerForm, description: e.target.value })
              }
            />
          </Field>
          <button className="btn" type="submit">
            Add
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Ledger">
        {ledger.isLoading ? <Loading /> : null}
        {!ledger.isLoading && !(ledger.data || []).length ? <Empty /> : null}
        {(ledger.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(ledger.data || []).map((row, idx) => (
                  <tr key={Number(row.id) || idx}>
                    <td>{String(row.date || '')}</td>
                    <td>{String(row.entry_type || row.type || '')}</td>
                    <td>{String(row.description || '')}</td>
                    <td>
                      <Money value={Number(row.amount || row.debit || row.credit || 0)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>

      <Panel title="Add purchase order">
        {addPo.error ? <ErrorBox error={addPo.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addPo.mutate()
          }}
        >
          <Field label="Item name">
            <input
              required
              value={poForm.item_name}
              onChange={(e) => setPoForm({ ...poForm, item_name: e.target.value })}
            />
          </Field>
          <Field label="Invoice / PO #">
            <input
              value={poForm.invoice_no}
              onChange={(e) => setPoForm({ ...poForm, invoice_no: e.target.value })}
              placeholder="auto if blank"
            />
          </Field>
          <Field label="Inventory ID">
            <input
              value={poForm.inventory_id}
              onChange={(e) => setPoForm({ ...poForm, inventory_id: e.target.value })}
              placeholder="required for GRN"
            />
          </Field>
          <Field label="Qty">
            <input
              type="number"
              min={1}
              value={poForm.quantity}
              onChange={(e) => setPoForm({ ...poForm, quantity: Number(e.target.value) })}
            />
          </Field>
          <Field label="Rate">
            <input
              type="number"
              step="0.01"
              min={0}
              value={poForm.rate}
              onChange={(e) => setPoForm({ ...poForm, rate: Number(e.target.value) })}
            />
          </Field>
          <Field label="Date">
            <input
              type="date"
              value={poForm.date}
              onChange={(e) => setPoForm({ ...poForm, date: e.target.value })}
            />
          </Field>
          <Field label="Status">
            <select
              value={poForm.status}
              onChange={(e) => setPoForm({ ...poForm, status: e.target.value })}
            >
              <option value="draft">Draft</option>
              <option value="ordered">Ordered</option>
            </select>
          </Field>
          <button className="btn" type="submit">
            Add PO
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Purchase orders">
        {receivePo.error ? <ErrorBox error={receivePo.error} /> : null}
        {!pos.isLoading && !(pos.data || []).length ? <Empty /> : null}
        {(pos.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Item</th>
                  <th>Ordered</th>
                  <th>Received</th>
                  <th>Rate</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(pos.data || []).map((row, idx) => {
                  const poId = Number(row.id) || 0
                  const remaining = Number(
                    row.qty_remaining ??
                      Number(row.quantity || 0) - Number(row.qty_received || 0),
                  )
                  return (
                    <tr key={poId || idx}>
                      <td>{String(row.id || '')}</td>
                      <td>{String(row.item_name || row.description || '')}</td>
                      <td>{String(row.quantity || '')}</td>
                      <td>{String(row.qty_received || 0)}</td>
                      <td>
                        <Money value={Number(row.rate || row.amount || 0)} />
                      </td>
                      <td>{String(row.status || '')}</td>
                      <td className="row-actions">
                        {row.status === 'draft' ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => orderPo.mutate(poId)}
                          >
                            Order
                          </button>
                        ) : null}
                        {remaining > 0 &&
                        row.status !== 'draft' &&
                        row.status !== 'closed' ? (
                          <>
                            <input
                              type="number"
                              min={1}
                              max={remaining}
                              style={{ width: 64 }}
                              value={receiveQty[poId] ?? remaining}
                              onChange={(e) =>
                                setReceiveQty({
                                  ...receiveQty,
                                  [poId]: Number(e.target.value),
                                })
                              }
                            />
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() =>
                                receivePo.mutate({
                                  po: row,
                                  qty: receiveQty[poId] ?? remaining,
                                })
                              }
                            >
                              Receive
                            </button>
                          </>
                        ) : null}
                        {row.status === 'received' || row.status === 'partial' ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => closePo.mutate(poId)}
                          >
                            Close
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </div>
  )
}

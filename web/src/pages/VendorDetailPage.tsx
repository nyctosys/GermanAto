import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import { EntitySelect } from '../components/EntitySelect'
import { UnitSelect } from '../components/UnitSelect'
import {
  Dialog,
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
  document_no?: string
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
  unit?: string | null
  expected_delivery?: string | null
}

type LedgerRow = {
  id?: number
  date?: string
  entry_type?: string
  description?: string
  debit?: number
  credit?: number
  amount?: number
  balance?: number
}

type GrnRow = {
  id: number
  document_no?: string
  purchase_order_id?: number
  quantity?: number
  unit_cost?: number
  amount?: number
  status?: string
  supplier_invoice_id?: number | null
}

type InvRow = {
  id: number
  document_no?: string
  supplier_invoice_no?: string
  amount?: number
  amount_paid?: number
  amount_due?: number
  status?: string
  due_date?: string | null
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function downloadStatementCsv(
  vendorName: string,
  entries: LedgerRow[],
  closing: number,
) {
  const lines = [
    'Date,Type,Description,Debit,Credit,Balance',
    ...entries.map((e) =>
      [
        e.date || '',
        e.entry_type || '',
        `"${String(e.description || '').replace(/"/g, '""')}"`,
        e.debit ?? '',
        e.credit ?? '',
        e.balance ?? '',
      ].join(','),
    ),
    `,,,,,${closing}`,
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `vendor-statement-${vendorName || 'vendor'}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function VendorDetailPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const [tab, setTab] = useState<'ledger' | 'pos' | 'grn' | 'invoices'>('pos')
  const [receiveTarget, setReceiveTarget] = useState<{ po: PoRow; qty: number } | null>(
    null,
  )
  const [receiptFile, setReceiptFile] = useState<File | null>(null)
  const [ledgerForm, setLedgerForm] = useState(() => ({
    amount: 0,
    description: '',
    entry_type: 'credit',
    date: todayIso(),
    payment_notes: '',
  }))
  const [poForm, setPoForm] = useState(() => ({
    item_name: '',
    invoice_no: '',
    quantity: 1,
    rate: 0,
    inventory_id: null as number | null,
    inventory_label: '',
    unit: 'pcs',
    expected_delivery: '',
    status: 'draft',
    date: todayIso(),
  }))
  const [receiveQty, setReceiveQty] = useState<Record<number, number>>({})
  const [payForm, setPayForm] = useState(() => ({
    amount: 0,
    date: todayIso(),
    method: 'cash',
    reference: '',
    supplier_invoice_id: '',
    notes: '',
  }))
  const [invoiceForm, setInvoiceForm] = useState(() => ({
    goods_receipt_id: '',
    supplier_invoice_no: '',
    amount: 0,
    date: todayIso(),
    due_date: '',
  }))
  const [creditForm, setCreditForm] = useState(() => ({
    goods_receipt_id: '',
    quantity: 1,
    unit_cost: 0,
    reason: 'Return to supplier',
    refund_amount: 0,
  }))

  const vendor = useQuery({
    queryKey: ['vendor', id],
    enabled: !!id,
    queryFn: () => api.get<Record<string, unknown>>(`/api/vendors/${id}`),
  })

  const summary = useQuery({
    queryKey: ['vendor-summary', id],
    enabled: !!id,
    queryFn: () =>
      api.get<{
        outstanding_balance?: number
        purchase_order_count?: number
        open_invoice_count?: number
      }>(`/api/vendors/${id}/summary`),
  })

  const ledger = useQuery({
    queryKey: ['vendor-ledger', id],
    enabled: !!id,
    queryFn: async () => {
      const data = await api.get<LedgerRow[] | { entries?: LedgerRow[] }>(
        `/api/vendors/${id}/ledger`,
      )
      return Array.isArray(data) ? data : data.entries || []
    },
  })

  const statement = useQuery({
    queryKey: ['vendor-statement', id],
    enabled: !!id,
    queryFn: () =>
      api.get<{
        entries?: LedgerRow[]
        closing_balance?: number
        total_debit?: number
        total_credit?: number
      }>(`/api/vendors/${id}/statement`),
  })

  const pos = useQuery({
    queryKey: ['vendor-pos', id],
    enabled: !!id,
    queryFn: async () => {
      const data = await api.get<{ purchase_orders?: PoRow[] } | PoRow[]>(
        `/api/vendors/${id}/purchase-orders`,
      )
      return Array.isArray(data) ? data : data.purchase_orders || []
    },
  })

  const grns = useQuery({
    queryKey: ['vendor-grn', id],
    enabled: !!id && tab === 'grn',
    queryFn: () =>
      api.get<{ goods_receipts?: GrnRow[] }>(`/api/vendors/${id}/goods-receipts`),
  })

  const invoices = useQuery({
    queryKey: ['vendor-invoices', id],
    enabled: !!id && (tab === 'invoices' || tab === 'ledger'),
    queryFn: () =>
      api.get<{ supplier_invoices?: InvRow[] }>(
        `/api/vendors/${id}/supplier-invoices`,
      ),
  })

  function invalidateAll() {
    qc.invalidateQueries({ queryKey: ['vendor-ledger', id] })
    qc.invalidateQueries({ queryKey: ['vendor-statement', id] })
    qc.invalidateQueries({ queryKey: ['vendor-pos', id] })
    qc.invalidateQueries({ queryKey: ['vendor-grn', id] })
    qc.invalidateQueries({ queryKey: ['vendor-invoices', id] })
    qc.invalidateQueries({ queryKey: ['vendor-summary', id] })
    qc.invalidateQueries({ queryKey: ['inventory'] })
  }

  const addLedger = useMutation({
    mutationFn: () =>
      api.post(
        '/api/ledger/add',
        {
          vendor_id: Number(id),
          ...ledgerForm,
          amount: Number(ledgerForm.amount),
        },
        { reason: 'Vendor ledger entry' },
      ),
    onSuccess: () => {
      invalidateAll()
      setLedgerForm({
        amount: 0,
        description: '',
        entry_type: 'credit',
        date: todayIso(),
        payment_notes: '',
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
        expected_delivery: poForm.expected_delivery || undefined,
        status: poForm.status,
        unit: poForm.unit,
        inventory_id: poForm.inventory_id || undefined,
      }),
    onSuccess: () => {
      invalidateAll()
      setPoForm({
        item_name: '',
        invoice_no: '',
        quantity: 1,
        rate: 0,
        inventory_id: null,
        inventory_label: '',
        unit: 'pcs',
        expected_delivery: '',
        status: 'draft',
        date: todayIso(),
      })
    },
  })

  const approvePo = useMutation({
    mutationFn: (poId: number) => api.post(`/api/purchase-orders/${poId}/approve`, {}),
    onSuccess: invalidateAll,
  })

  const orderPo = useMutation({
    mutationFn: (poId: number) =>
      api.put(`/api/purchase-orders/${poId}/status`, { status: 'ordered' }),
    onSuccess: invalidateAll,
  })

  const receivePo = useMutation({
    mutationFn: async ({
      po,
      qty,
      file,
    }: {
      po: PoRow
      qty: number
      file?: File | null
    }) => {
      const reason = 'PO goods receive'
      if (file) {
        const fd = new FormData()
        fd.append('quantity', String(qty))
        fd.append('verified_qty', String(qty))
        fd.append('unit_cost', String(po.rate ?? 0))
        if (po.inventory_id) fd.append('inventory_id', String(po.inventory_id))
        fd.append('receipt', file)
        return api.post(`/api/purchase-orders/${po.id}/receive`, fd, { reason })
      }
      return api.post(
        `/api/purchase-orders/${po.id}/receive`,
        {
          quantity: qty,
          verified_qty: qty,
          unit_cost: po.rate,
          inventory_id: po.inventory_id,
        },
        { reason },
      )
    },
    onSuccess: () => {
      setReceiveTarget(null)
      setReceiptFile(null)
      invalidateAll()
    },
  })

  const closePo = useMutation({
    mutationFn: (poId: number) =>
      api.put(`/api/purchase-orders/${poId}/status`, { status: 'closed' }),
    onSuccess: invalidateAll,
  })

  async function onClosePo(poId: number) {
    if (
      await confirm({
        title: 'Close purchase order',
        message: 'Close this PO? You will not be able to receive more against it.',
        confirmLabel: 'Close PO',
        cancelLabel: 'Cancel',
      })
    ) {
      closePo.mutate(poId)
    }
  }

  const createInvoice = useMutation({
    mutationFn: () =>
      api.post(
        '/api/supplier-invoices',
        {
          vendor_id: Number(id),
          goods_receipt_id: invoiceForm.goods_receipt_id
            ? Number(invoiceForm.goods_receipt_id)
            : undefined,
          supplier_invoice_no: invoiceForm.supplier_invoice_no,
          amount: Number(invoiceForm.amount),
          date: invoiceForm.date,
          due_date: invoiceForm.due_date || undefined,
        },
        { reason: 'Supplier invoice recorded' },
      ),
    onSuccess: () => {
      invalidateAll()
      setInvoiceForm({
        goods_receipt_id: '',
        supplier_invoice_no: '',
        amount: 0,
        date: todayIso(),
        due_date: '',
      })
    },
  })

  const createPayment = useMutation({
    mutationFn: () =>
      api.post(
        '/api/supplier-payments',
        {
          vendor_id: Number(id),
          amount: Number(payForm.amount),
          date: payForm.date,
          method: payForm.method,
          reference: payForm.reference || undefined,
          supplier_invoice_id: payForm.supplier_invoice_id
            ? Number(payForm.supplier_invoice_id)
            : undefined,
          notes: payForm.notes || undefined,
        },
        { reason: 'Supplier payment recorded' },
      ),
    onSuccess: () => {
      invalidateAll()
      setPayForm({
        amount: 0,
        date: todayIso(),
        method: 'cash',
        reference: '',
        supplier_invoice_id: '',
        notes: '',
      })
    },
  })

  const createCredit = useMutation({
    mutationFn: () =>
      api.post(
        '/api/supplier-credit-notes',
        {
          vendor_id: Number(id),
          goods_receipt_id: creditForm.goods_receipt_id
            ? Number(creditForm.goods_receipt_id)
            : undefined,
          quantity: Number(creditForm.quantity),
          unit_cost: Number(creditForm.unit_cost),
          amount: Number(creditForm.quantity) * Number(creditForm.unit_cost),
          refund_amount: Number(creditForm.refund_amount) || 0,
          reason: creditForm.reason,
        },
        { reason: creditForm.reason || 'Supplier credit note' },
      ),
    onSuccess: () => {
      invalidateAll()
      setCreditForm({
        goods_receipt_id: '',
        quantity: 1,
        unit_cost: 0,
        reason: 'Return to supplier',
        refund_amount: 0,
      })
    },
  })

  async function autofillFromInventory(inventoryId: number, label: string) {
    try {
      const data = await api.get<{
        known_rate?: number
        unit?: string
        item_name?: string
      }>(
        `/api/purchase-orders/known-rate?vendor_id=${id}&inventory_id=${inventoryId}`,
      )
      setPoForm((f) => ({
        ...f,
        inventory_id: inventoryId,
        inventory_label: label,
        item_name: data.item_name || f.item_name || label,
        rate: Number(data.known_rate || 0),
        unit: data.unit || 'pcs',
      }))
    } catch {
      setPoForm((f) => ({
        ...f,
        inventory_id: inventoryId,
        inventory_label: label,
      }))
    }
  }

  if (vendor.isLoading) return <Loading />
  if (vendor.error) return <ErrorBox error={vendor.error} />

  const v = vendor.data || {}
  const outstanding = Number(summary.data?.outstanding_balance || 0)

  return (
    <div>
      <Dialog
        open={Boolean(receiveTarget)}
        title="Receive goods"
        onClose={() => {
          if (receivePo.isPending) return
          setReceiveTarget(null)
          setReceiptFile(null)
        }}
      >
        <p>
          Record GRN for{' '}
          <strong>{receiveTarget?.po.item_name || 'item'}</strong> — qty{' '}
          <strong>{receiveTarget?.qty ?? 0}</strong>. This updates stock only;
          record the supplier invoice separately to create a payable.
        </p>
        <Field label="Supplier receipt (optional)">
          <input
            type="file"
            accept="image/*,.pdf,.png,.jpg,.jpeg,.webp"
            onChange={(e) => setReceiptFile(e.target.files?.[0] || null)}
          />
        </Field>
        {receivePo.error ? <ErrorBox error={receivePo.error} /> : null}
        <div className="dialog-actions">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={receivePo.isPending}
            onClick={() => {
              setReceiveTarget(null)
              setReceiptFile(null)
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn"
            disabled={receivePo.isPending || !receiveTarget}
            onClick={() => {
              if (!receiveTarget) return
              receivePo.mutate({
                po: receiveTarget.po,
                qty: receiveTarget.qty,
                file: receiptFile,
              })
            }}
          >
            {receivePo.isPending ? 'Receiving…' : 'Continue'}
          </button>
        </div>
      </Dialog>

      <PageHeader
        title={String(v.name || `Vendor #${id}`)}
        actions={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() =>
                downloadStatementCsv(
                  String(v.name || id),
                  statement.data?.entries || [],
                  Number(statement.data?.closing_balance || outstanding),
                )
              }
            >
              Export statement
            </button>
            <Link className="btn btn-secondary" to="/vendors">
              Back
            </Link>
          </>
        }
      />

      <Panel title="Details">
        <p>
          {String(v.code || '')} · {String(v.company_name || '')} ·{' '}
          {String(v.contact_person || '')} · {String(v.phone || '')}
        </p>
        <p className="muted">{String(v.address || '')}</p>
        <p>
          Payment terms: {String(v.payment_terms_days ?? 30)} days · Outstanding:{' '}
          <Money value={outstanding} /> · Open invoices:{' '}
          {String(summary.data?.open_invoice_count ?? '—')}
        </p>
      </Panel>

      <div className="row-actions" style={{ marginBottom: 12, gap: 8 }}>
        {(
          [
            ['pos', 'Purchase orders'],
            ['grn', 'Goods receipts'],
            ['invoices', 'Invoices & payments'],
            ['ledger', 'Ledger'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? 'btn btn-sm' : 'btn btn-secondary btn-sm'}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'pos' ? (
        <>
          <Panel title="Add purchase order">
            {addPo.error ? <ErrorBox error={addPo.error} /> : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                addPo.mutate()
              }}
            >
              <EntitySelect
                label="Inventory item"
                type="inventory"
                valueId={poForm.inventory_id}
                displayValue={poForm.inventory_label}
                onSelect={(hit) => {
                  if (!hit) {
                    setPoForm((f) => ({
                      ...f,
                      inventory_id: null,
                      inventory_label: '',
                      item_name: '',
                      unit: 'pcs',
                      rate: 0,
                      quantity: 1,
                    }))
                    return
                  }
                  void autofillFromInventory(hit.id, hit.label)
                }}
              />
              <Field label="Item name">
                <input
                  required
                  value={poForm.item_name}
                  onChange={(e) => setPoForm({ ...poForm, item_name: e.target.value })}
                />
              </Field>
              <UnitSelect
                value={poForm.unit}
                onChange={(unit) => setPoForm({ ...poForm, unit })}
                required
              />
              <Field label="Qty">
                <input
                  type="number"
                  min={1}
                  value={poForm.quantity}
                  onChange={(e) =>
                    setPoForm({ ...poForm, quantity: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Rate (known supplier / avg)">
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  value={poForm.rate}
                  onChange={(e) =>
                    setPoForm({ ...poForm, rate: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Expected delivery">
                <input
                  type="date"
                  value={poForm.expected_delivery}
                  onChange={(e) =>
                    setPoForm({ ...poForm, expected_delivery: e.target.value })
                  }
                />
              </Field>
              <button className="btn" type="submit" disabled={addPo.isPending}>
                Add draft PO
              </button>
            </FormGrid>
          </Panel>

          <Panel title="Purchase orders">
            {receivePo.error ? <ErrorBox error={receivePo.error} /> : null}
            {approvePo.error ? <ErrorBox error={approvePo.error} /> : null}
            {!pos.isLoading && !(pos.data || []).length ? <Empty /> : null}
            {(pos.data || []).length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Doc</th>
                      <th>Item</th>
                      <th>Ordered</th>
                      <th>Received</th>
                      <th>Rate</th>
                      <th>ETA</th>
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
                          <td>{String(row.document_no || row.id || '')}</td>
                          <td>
                            {String(row.item_name || '')}
                            {row.unit ? ` (${row.unit})` : ''}
                          </td>
                          <td>{String(row.quantity || '')}</td>
                          <td>{String(row.qty_received || 0)}</td>
                          <td>
                            <Money value={Number(row.rate || 0)} />
                          </td>
                          <td>{String(row.expected_delivery || '—')}</td>
                          <td>{String(row.status || '')}</td>
                          <td className="row-actions">
                            {row.status === 'draft' ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => approvePo.mutate(poId)}
                              >
                                Approve
                              </button>
                            ) : null}
                            {row.status === 'approved' || row.status === 'draft' ? (
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
                              onClick={() => {
                                setReceiptFile(null)
                                setReceiveTarget({
                                  po: row,
                                  qty: receiveQty[poId] ?? remaining,
                                })
                              }}
                            >
                              Receive
                            </button>
                          </>
                        ) : null}
                        {row.status === 'received' || row.status === 'partial' ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => void onClosePo(poId)}
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
        </>
      ) : null}

      {tab === 'grn' ? (
        <>
          <Panel title="Goods receipts">
            {grns.isLoading ? <Loading /> : null}
            {!grns.isLoading && !(grns.data?.goods_receipts || []).length ? (
              <Empty>No goods receipts yet. Receive against an ordered PO.</Empty>
            ) : null}
            {(grns.data?.goods_receipts || []).length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>GRN</th>
                      <th>PO</th>
                      <th>Qty</th>
                      <th>Amount</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(grns.data?.goods_receipts || []).map((g) => (
                      <tr key={g.id}>
                        <td>{g.document_no || g.id}</td>
                        <td>{g.purchase_order_id}</td>
                        <td>{g.quantity}</td>
                        <td>
                          <Money value={Number(g.amount || 0)} />
                        </td>
                        <td>{g.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Panel>

          <Panel title="Record supplier invoice from GRN">
            {createInvoice.error ? <ErrorBox error={createInvoice.error} /> : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                createInvoice.mutate()
              }}
            >
              <Field label="GRN id">
                <input
                  required
                  value={invoiceForm.goods_receipt_id}
                  onChange={(e) => {
                    const gid = e.target.value
                    const grn = (grns.data?.goods_receipts || []).find(
                      (g) => String(g.id) === gid,
                    )
                    setInvoiceForm({
                      ...invoiceForm,
                      goods_receipt_id: gid,
                      amount: grn ? Number(grn.amount || 0) : invoiceForm.amount,
                    })
                  }}
                />
              </Field>
              <Field label="Supplier invoice #">
                <input
                  required
                  value={invoiceForm.supplier_invoice_no}
                  onChange={(e) =>
                    setInvoiceForm({
                      ...invoiceForm,
                      supplier_invoice_no: e.target.value,
                    })
                  }
                />
              </Field>
              <Field label="Amount">
                <input
                  type="number"
                  step="0.01"
                  value={invoiceForm.amount}
                  onChange={(e) =>
                    setInvoiceForm({
                      ...invoiceForm,
                      amount: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="Invoice date">
                <input
                  type="date"
                  value={invoiceForm.date}
                  onChange={(e) =>
                    setInvoiceForm({ ...invoiceForm, date: e.target.value })
                  }
                />
              </Field>
              <Field label="Due date">
                <input
                  type="date"
                  value={invoiceForm.due_date}
                  onChange={(e) =>
                    setInvoiceForm({ ...invoiceForm, due_date: e.target.value })
                  }
                  title="Leave blank to use vendor payment terms"
                />
              </Field>
              <button className="btn" type="submit">
                Create payable
              </button>
            </FormGrid>
          </Panel>

          <Panel title="Return / credit note">
            {createCredit.error ? <ErrorBox error={createCredit.error} /> : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                createCredit.mutate()
              }}
            >
              <Field label="GRN id">
                <input
                  value={creditForm.goods_receipt_id}
                  onChange={(e) =>
                    setCreditForm({ ...creditForm, goods_receipt_id: e.target.value })
                  }
                />
              </Field>
              <Field label="Qty to return">
                <input
                  type="number"
                  min={0}
                  value={creditForm.quantity}
                  onChange={(e) =>
                    setCreditForm({
                      ...creditForm,
                      quantity: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="Unit cost">
                <input
                  type="number"
                  step="0.01"
                  value={creditForm.unit_cost}
                  onChange={(e) =>
                    setCreditForm({
                      ...creditForm,
                      unit_cost: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="Cash refund (optional)">
                <input
                  type="number"
                  step="0.01"
                  value={creditForm.refund_amount}
                  onChange={(e) =>
                    setCreditForm({
                      ...creditForm,
                      refund_amount: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="Reason">
                <input
                  required
                  value={creditForm.reason}
                  onChange={(e) =>
                    setCreditForm({ ...creditForm, reason: e.target.value })
                  }
                />
              </Field>
              <button className="btn" type="submit">
                Post credit note
              </button>
            </FormGrid>
          </Panel>
        </>
      ) : null}

      {tab === 'invoices' ? (
        <>
          <Panel title="Supplier invoices">
            {invoices.isLoading ? <Loading /> : null}
            {!(invoices.data?.supplier_invoices || []).length ? <Empty /> : null}
            {(invoices.data?.supplier_invoices || []).length > 0 ? (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Doc</th>
                      <th>Supplier #</th>
                      <th>Amount</th>
                      <th>Due</th>
                      <th>Paid</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(invoices.data?.supplier_invoices || []).map((inv) => (
                      <tr key={inv.id}>
                        <td>{inv.document_no || inv.id}</td>
                        <td>{inv.supplier_invoice_no}</td>
                        <td>
                          <Money value={Number(inv.amount || 0)} />
                        </td>
                        <td>{inv.due_date || '—'}</td>
                        <td>
                          <Money value={Number(inv.amount_paid || 0)} />
                        </td>
                        <td>{inv.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Panel>

          <Panel title="Record supplier payment">
            {createPayment.error ? <ErrorBox error={createPayment.error} /> : null}
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                createPayment.mutate()
              }}
            >
              <Field label="Amount">
                <input
                  type="number"
                  step="0.01"
                  required
                  value={payForm.amount}
                  onChange={(e) =>
                    setPayForm({ ...payForm, amount: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Invoice id (optional)">
                <input
                  value={payForm.supplier_invoice_id}
                  onChange={(e) =>
                    setPayForm({ ...payForm, supplier_invoice_id: e.target.value })
                  }
                />
              </Field>
              <Field label="Method">
                <select
                  value={payForm.method}
                  onChange={(e) => setPayForm({ ...payForm, method: e.target.value })}
                >
                  <option value="cash">Cash</option>
                  <option value="bank">Bank</option>
                  <option value="cheque">Cheque</option>
                </select>
              </Field>
              <Field label="Reference">
                <input
                  value={payForm.reference}
                  onChange={(e) =>
                    setPayForm({ ...payForm, reference: e.target.value })
                  }
                />
              </Field>
              <Field label="Payment date">
                <input
                  type="date"
                  value={payForm.date}
                  onChange={(e) => setPayForm({ ...payForm, date: e.target.value })}
                />
              </Field>
              <button className="btn" type="submit">
                Record payment
              </button>
            </FormGrid>
          </Panel>
        </>
      ) : null}

      {tab === 'ledger' ? (
        <>
          <Panel title="Add ledger entry">
            {addLedger.error ? <ErrorBox error={addLedger.error} /> : null}
            <p className="muted">
              Prefer Invoices &amp; payments for AP. Manual ledger is for adjustments.
            </p>
            <FormGrid
              onSubmit={(e: FormEvent) => {
                e.preventDefault()
                addLedger.mutate()
              }}
            >
              <Field label="Entry date">
                <input
                  type="date"
                  value={ledgerForm.date}
                  onChange={(e) =>
                    setLedgerForm({ ...ledgerForm, date: e.target.value })
                  }
                />
              </Field>
              <Field label="Type">
                <select
                  value={ledgerForm.entry_type}
                  onChange={(e) =>
                    setLedgerForm({ ...ledgerForm, entry_type: e.target.value })
                  }
                >
                  <option value="debit">Debit (payable ↑)</option>
                  <option value="credit">Credit (payment ↓)</option>
                </select>
              </Field>
              <Field label="Amount">
                <input
                  type="number"
                  step="0.01"
                  value={ledgerForm.amount}
                  onChange={(e) =>
                    setLedgerForm({
                      ...ledgerForm,
                      amount: Number(e.target.value),
                    })
                  }
                />
              </Field>
              <Field label="Description">
                <input
                  required
                  value={ledgerForm.description}
                  onChange={(e) =>
                    setLedgerForm({
                      ...ledgerForm,
                      description: e.target.value,
                    })
                  }
                />
              </Field>
              <button className="btn" type="submit">
                Add
              </button>
            </FormGrid>
          </Panel>

          <Panel
            title="Ledger"
            actions={
              statement.data ? (
                <span className="muted">
                  Debit <Money value={Number(statement.data.total_debit || 0)} /> ·
                  Credit <Money value={Number(statement.data.total_credit || 0)} /> ·
                  Close <Money value={Number(statement.data.closing_balance || 0)} />
                </span>
              ) : null
            }
          >
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
                      <th>Debit</th>
                      <th>Credit</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(ledger.data || []).map((row, idx) => (
                      <tr key={Number(row.id) || idx}>
                        <td>{String(row.date || '')}</td>
                        <td>{String(row.entry_type || '')}</td>
                        <td>{String(row.description || '')}</td>
                        <td>
                          <Money value={Number(row.debit || 0)} />
                        </td>
                        <td>
                          <Money value={Number(row.credit || 0)} />
                        </td>
                        <td>
                          <Money value={Number(row.balance || 0)} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Panel>
        </>
      ) : null}
    </div>
  )
}

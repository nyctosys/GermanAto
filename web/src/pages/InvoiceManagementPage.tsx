import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import {
  Empty,
  ErrorBox,
  Loading,
  Money,
  PageHeader,
  Panel,
} from '../components/ui'

type InvoiceRow = {
  id: number
  document_no?: string | null
  customer_name?: string
  customer_reg_no?: string
  status?: string
  type_of?: string
  net_total?: number
  amount_due?: number
  amount_paid?: number
  amount_unpaid?: number
  balance?: number
  locked?: boolean
  repair_order_id?: number | null
  created_at?: string
}

export function InvoiceManagementPage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
  const [sp] = useSearchParams()
  const [keyword, setKeyword] = useState(sp.get('q') || '')
  const [status, setStatus] = useState(sp.get('status') || 'all')
  const [dateFrom, setDateFrom] = useState(sp.get('start_date') || sp.get('date_from') || '')
  const [dateTo, setDateTo] = useState(sp.get('end_date') || sp.get('date_to') || '')
  const [payId, setPayId] = useState<number | null>(null)
  const [payAmount, setPayAmount] = useState('')
  const [creditId, setCreditId] = useState<number | null>(null)
  const [creditAmount, setCreditAmount] = useState('')
  const [creditReason, setCreditReason] = useState('')

  const q = useQuery({
    queryKey: ['invoices', keyword, status, dateFrom, dateTo],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('type', 'invoice')
      if (keyword.trim()) params.set('q', keyword.trim())
      if (status !== 'all') params.set('status', status)
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      const data = await api.get<{ invoices?: InvoiceRow[] }>(`/api/search?${params}`)
      return data.invoices || []
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) =>
      api.delete(`/api/invoice/${id}/delete`, { reason: 'Invoice deleted' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invoices'] }),
  })

  const payM = useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      api.put(
        `/api/invoice/${id}/update-balance`,
        { paid_amount: amount },
        { reason: `Payment ${amount} PKR` },
      ),
    onSuccess: () => {
      setPayId(null)
      setPayAmount('')
      qc.invalidateQueries({ queryKey: ['invoices'] })
    },
  })

  const creditM = useMutation({
    mutationFn: ({
      id,
      amount,
      reason,
    }: {
      id: number
      amount: number
      reason: string
    }) =>
      api.post(
        `/api/invoice/${id}/credit-note`,
        { amount, reason },
        { reason },
      ),
    onSuccess: () => {
      setCreditId(null)
      setCreditAmount('')
      setCreditReason('')
      qc.invalidateQueries({ queryKey: ['invoices'] })
    },
  })

  return (
    <div>
      <PageHeader
        title="Invoices"
        actions={
          <>
            <Link className="btn btn-secondary" to="/quotes/pending">
              From quotes
            </Link>
            <Link className="btn" to="/invoices/new">
              New invoice
            </Link>
          </>
        }
      />
      <Panel title="Filters">
        <div className="form-grid">
          <input
            className="input"
            placeholder="Search name, phone, plate, INV-…"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="unpaid">Unpaid</option>
            <option value="partially_paid">Partially paid</option>
            <option value="paid">Paid</option>
          </select>
          <input
            className="input"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <input
            className="input"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
      </Panel>

      {[payM, creditM, remove].map((m, i) =>
        m.error ? <ErrorBox key={i} error={m.error} /> : null,
      )}

      <Panel title="Results">
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {!q.isLoading && !(q.data || []).length ? <Empty /> : null}
        {(q.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Invoice #</th>
                  <th>Customer</th>
                  <th>Vehicle</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Paid</th>
                  <th>Unpaid</th>
                  <th>Date</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((inv) => (
                  <tr key={inv.id}>
                    <td>
                      <strong>{inv.document_no || `#${inv.id}`}</strong>
                      {inv.locked ? <div className="muted">Locked (paid)</div> : null}
                      {inv.repair_order_id ? (
                        <div className="muted">RO #{inv.repair_order_id}</div>
                      ) : null}
                    </td>
                    <td>{inv.customer_name}</td>
                    <td>{inv.customer_reg_no || '—'}</td>
                    <td>
                      <span
                        className={`status-pill ${
                          inv.status === 'paid'
                            ? 'is-ready'
                            : inv.status === 'partially_paid'
                              ? 'is-progress'
                              : 'is-waiting'
                        }`}
                      >
                        {inv.status}
                      </span>
                    </td>
                    <td>
                      <Money value={inv.amount_due ?? inv.net_total} />
                    </td>
                    <td>
                      <Money value={inv.amount_paid ?? 0} />
                    </td>
                    <td>
                      <Money value={inv.amount_unpaid ?? inv.balance} />
                    </td>
                    <td>{inv.created_at || '—'}</td>
                    <td className="row-actions">
                      <Link className="btn btn-secondary btn-sm" to={`/invoices/${inv.id}/print`}>
                        Print
                      </Link>
                      {!inv.locked ? (
                        <Link className="btn btn-secondary btn-sm" to={`/invoices/${inv.id}/edit`}>
                          Edit
                        </Link>
                      ) : (
                        <Link className="btn btn-secondary btn-sm" to={`/invoices/${inv.id}/edit`}>
                          View
                        </Link>
                      )}
                      {(inv.amount_unpaid ?? inv.balance ?? 0) > 0 ? (
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => {
                            setPayId(inv.id)
                            setPayAmount(String(inv.amount_unpaid ?? inv.balance ?? ''))
                          }}
                        >
                          Record payment
                        </button>
                      ) : null}
                      {inv.locked ? (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            setCreditId(inv.id)
                            setCreditAmount('')
                            setCreditReason('')
                          }}
                        >
                          Credit note
                        </button>
                      ) : null}
                      {!inv.locked ? (
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={async () => {
                            if (
                              await confirm({
                                message: 'Delete this invoice?',
                                danger: true,
                                confirmLabel: 'Delete',
                              })
                            )
                              remove.mutate(inv.id)
                          }}
                        >
                          Delete
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>

      {payId != null ? (
        <Panel title={`Record payment — invoice #${payId}`}>
          <div className="form-grid">
            <label className="field">
              <span>Amount (PKR)</span>
              <input
                className="input"
                type="number"
                min={0.01}
                step="0.01"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
              />
            </label>
            <div className="row-actions">
              <button
                type="button"
                className="btn"
                disabled={payM.isPending || !(Number(payAmount) > 0)}
                onClick={() =>
                  payM.mutate({ id: payId, amount: Number(payAmount) })
                }
              >
                Apply payment
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setPayId(null)}
              >
                Cancel
              </button>
            </div>
          </div>
          <p className="muted">
            Payments update unpaid balance only. Invoice total (accrual) does not change.
          </p>
        </Panel>
      ) : null}

      {creditId != null ? (
        <Panel title={`Credit note — invoice #${creditId}`}>
          <div className="form-grid">
            <label className="field">
              <span>Amount (PKR)</span>
              <input
                className="input"
                type="number"
                min={0.01}
                step="0.01"
                value={creditAmount}
                onChange={(e) => setCreditAmount(e.target.value)}
              />
            </label>
            <label className="field">
              <span>Reason (required)</span>
              <input
                className="input"
                value={creditReason}
                onChange={(e) => setCreditReason(e.target.value)}
                placeholder="Authorized reversal reason"
              />
            </label>
            <div className="row-actions">
              <button
                type="button"
                className="btn"
                disabled={
                  creditM.isPending ||
                  !(Number(creditAmount) > 0) ||
                  !creditReason.trim()
                }
                onClick={() =>
                  creditM.mutate({
                    id: creditId,
                    amount: Number(creditAmount),
                    reason: creditReason.trim(),
                  })
                }
              >
                Post credit note
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setCreditId(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </Panel>
      ) : null}
    </div>
  )
}

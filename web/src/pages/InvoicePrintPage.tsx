import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Loading, Money } from '../components/ui'
import { PrintShell } from '../print/PrintShell'

type InvoiceDetail = {
  id: number
  document_no?: string | null
  customer_name?: string
  customer_phone?: string
  customer_address?: string
  customer_reg_no?: string
  customer_made?: string
  customer_mileage?: string
  customer_vin?: string | null
  created_at?: string
  status?: string
  amount_due?: number
  amount_paid?: number
  amount_unpaid?: number
  net_total?: number
  tax_amount?: number
  discount?: number
  advance?: number
  paid_amount?: number
  include_tax?: boolean
  repair_order_id?: number | null
  job_card_id?: number | null
  items?: Array<{
    product_name: string
    part_number?: string | null
    quantity: number
    price: number
    approval_status?: string
  }>
  labours?: Array<{
    description: string
    price: number
    approval_status?: string
  }>
  payments_history?: Array<{ amount: number; timestamp?: string; person?: string }>
}

export function InvoicePrintPage() {
  const { id } = useParams()
  const q = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => api.get<InvoiceDetail>(`/api/invoice/${id}`),
    enabled: !!id,
  })

  if (q.isLoading) return <Loading />
  if (q.error) return <ErrorBox error={q.error} />
  const inv = q.data
  if (!inv) return <p className="muted">Invoice not found</p>

  return (
    <div>
      <p className="no-print" style={{ marginBottom: 12 }}>
        <Link className="btn btn-secondary" to="/invoices">
          ← Invoices
        </Link>
      </p>
      <PrintShell
        title={inv.document_no || `Invoice #${inv.id}`}
        meta={
          <>
            <div>Date: {inv.created_at || '—'}</div>
            <div>Status: {inv.status}</div>
            {inv.repair_order_id ? <div>RO #{inv.repair_order_id}</div> : null}
            {inv.job_card_id ? <div>Job card #{inv.job_card_id}</div> : null}
          </>
        }
      >
        <section style={{ marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 6px' }}>Bill to</h3>
          <p style={{ margin: 0 }}>
            <strong>{inv.customer_name}</strong>
            <br />
            {inv.customer_phone}
            <br />
            {inv.customer_address}
          </p>
          <p style={{ margin: '8px 0 0' }}>
            Vehicle: {inv.customer_made} · {inv.customer_reg_no}
            {inv.customer_mileage ? ` · ${inv.customer_mileage} km` : ''}
            {inv.customer_vin ? ` · VIN ${inv.customer_vin}` : ''}
          </p>
        </section>

        {(inv.labours || []).length > 0 ? (
          <section style={{ marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 6px' }}>Labour</h3>
            <table className="data">
              <thead>
                <tr>
                  <th>Description</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(inv.labours || []).map((l, i) => (
                  <tr key={i}>
                    <td>{l.description}</td>
                    <td>
                      <Money value={l.price} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}

        {(inv.items || []).length > 0 ? (
          <section style={{ marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 6px' }}>Parts</h3>
            <table className="data">
              <thead>
                <tr>
                  <th>Part</th>
                  <th>Qty</th>
                  <th>Rate</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(inv.items || []).map((it, i) => (
                  <tr key={i}>
                    <td>
                      {it.product_name}
                      {it.part_number ? (
                        <div className="muted">{it.part_number}</div>
                      ) : null}
                    </td>
                    <td>{it.quantity}</td>
                    <td>
                      <Money value={it.price} />
                    </td>
                    <td>
                      <Money value={it.price * it.quantity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}

        <section style={{ marginTop: 12, maxWidth: 320, marginLeft: 'auto' }}>
          <div style={{ display: 'grid', gap: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Subtotal</span>
              <Money value={inv.net_total} />
            </div>
            {inv.include_tax ? (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Tax</span>
                <Money value={inv.tax_amount} />
              </div>
            ) : null}
            {(inv.discount || 0) > 0 ? (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Discount / credit</span>
                <Money value={inv.discount} />
              </div>
            ) : null}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
              <span>Total due</span>
              <Money value={inv.amount_due ?? inv.net_total} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Paid (incl. advance)</span>
              <Money value={inv.amount_paid ?? 0} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
              <span>Outstanding</span>
              <Money value={inv.amount_unpaid ?? 0} />
            </div>
          </div>
        </section>

        {(inv.payments_history || []).length > 0 ? (
          <section style={{ marginTop: 20 }}>
            <h3 style={{ margin: '0 0 6px' }}>Payments</h3>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {(inv.payments_history || []).map((p, i) => (
                <li key={i}>
                  <Money value={p.amount} /> — {p.timestamp || '—'}
                  {p.person ? ` (${p.person})` : ''}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </PrintShell>
    </div>
  )
}

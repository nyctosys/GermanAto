import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  Empty,
  ErrorBox,
  Loading,
  Money,
  PageHeader,
  Panel,
  StatusBadge,
} from '../components/ui'
import { PrintShell } from '../print/PrintShell'

type Bundle = {
  estimate: {
    id: number
    document_no?: string
    approval_state?: string
    customer_name?: string
    customer_phone?: string
    customer_reg_no?: string
    customer_made?: string
    job_card_id?: number
    parent_quote_id?: number
    net_total?: number
    discount?: number
    tax_amount?: number
    include_tax?: boolean
    final_estimate?: number
    required_advance?: number
    advance_received?: number
    remaining_advance_due?: number
    expected_duration_hours?: number
    expected_completion_at?: string
    version?: number
    items?: Array<{
      id: number
      product_name: string
      quantity: number
      price: number
      line_total: number
      approval_status?: string
    }>
    labours?: Array<{
      id: number
      description: string
      price: number
      std_hours?: number
      approval_status?: string
    }>
  }
  money: {
    final_estimate: number
    required_advance: number
    advance_received: number
    remaining_advance_due: number
    is_revenue: boolean
    advances_are_liability: boolean
  }
  stock_gaps: Array<{
    product_name: string
    needed: number
    available: number
    missing: number
  }>
  deposits: Array<{ id: number; amount: number; status: string }>
  channels: string[]
  advance_policy: { mode?: string; percent?: number; fixed_amount?: number }
}

export function EstimateDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()

  const q = useQuery({
    queryKey: ['estimate', id],
    queryFn: () => api.get<Bundle>(`/api/estimates/${id}`),
    enabled: !!id,
  })

  const send = useMutation({
    mutationFn: () =>
      api.post<{ approval_url: string; channels_sent: string[] }>(`/api/estimates/${id}/send`, {
        public_base_url: window.location.origin,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['estimate', id] }),
  })

  const revise = useMutation({
    mutationFn: () =>
      api.post<{ id: number }>(`/api/estimates/${id}/revise`, {
        version: q.data?.estimate.version,
      }),
    onSuccess: (row) => nav(`/quotes/${row.id}`),
  })

  if (q.isLoading) return <Loading />
  if (q.error) return <ErrorBox error={q.error} />
  const data = q.data
  if (!data) return null
  const e = data.estimate
  const doc = e.document_no || `QT-${String(e.id).padStart(5, '0')}`

  return (
    <div>
      <PageHeader
        title={doc}
        actions={
          <>
            <StatusBadge status={e.approval_state || 'draft'} tone="info" />
            <button type="button" className="btn btn-secondary" onClick={() => window.print()}>
              Print
            </button>
            <button type="button" className="btn" disabled={send.isPending} onClick={() => send.mutate()}>
              Send for approval
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={revise.isPending || e.approval_state === 'revised'}
              onClick={() => revise.mutate()}
            >
              Revise (keep history)
            </button>
            {e.job_card_id ? (
              <Link className="btn btn-ghost" to={`/job-cards/${e.job_card_id}`}>
                Job card
              </Link>
            ) : null}
          </>
        }
      />

      {send.error ? <ErrorBox error={send.error} /> : null}
      {revise.error ? <ErrorBox error={revise.error} /> : null}
      {send.data ? (
        <p className="muted">
          Sent via {(send.data.channels_sent || []).join(', ') || 'link'}:{' '}
          <a href={send.data.approval_url}>{send.data.approval_url}</a>
        </p>
      ) : null}

      <Panel title="Customer">
        <p>
          {e.customer_name} · {e.customer_phone} · {e.customer_reg_no} · {e.customer_made}
        </p>
        {e.parent_quote_id ? (
          <p className="muted">
            Revised from <Link to={`/quotes/${e.parent_quote_id}`}>#{e.parent_quote_id}</Link>
          </p>
        ) : null}
        <p className="muted">
          Duration: {e.expected_duration_hours ?? '—'} h · Completion: {e.expected_completion_at || '—'}
        </p>
      </Panel>

      <Panel title="Money (estimate ≠ revenue)">
        <div className="stat-grid">
          <div className="stat">
            <div className="label">Final estimate</div>
            <div className="value">
              <Money value={data.money.final_estimate} />
            </div>
          </div>
          <div className="stat">
            <div className="label">Required advance</div>
            <div className="value">
              <Money value={data.money.required_advance} />
            </div>
          </div>
          <div className="stat">
            <div className="label">Advance received (liability)</div>
            <div className="value">
              <Money value={data.money.advance_received} />
            </div>
          </div>
          <div className="stat">
            <div className="label">Remaining advance due</div>
            <div className="value">
              <Money value={data.money.remaining_advance_due} />
            </div>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Policy: {data.advance_policy.mode}
          {data.advance_policy.mode === 'percent' ? ` ${data.advance_policy.percent}%` : ''}
          {data.advance_policy.mode === 'fixed' ? ` Rs ${data.advance_policy.fixed_amount}` : ''} ·
          Channels: {(data.channels || []).join(', ')} · Deposits stay liabilities until applied to an
          invoice.
        </p>
        {(data.deposits || []).length ? (
          <ul>
            {data.deposits.map((d) => (
              <li key={d.id}>
                Deposit #{d.id}: <Money value={d.amount} /> · {d.status}
              </li>
            ))}
          </ul>
        ) : (
          <Empty>No deposits recorded against this estimate yet</Empty>
        )}
        <p>
          <Link to="/money-in">Record / view deposits in Money In</Link>
        </p>
      </Panel>

      <Panel title="Stock availability">
        {(data.stock_gaps || []).length === 0 ? (
          <Empty>All parts available (or no inventory-linked lines)</Empty>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Part</th>
                  <th>Needed</th>
                  <th>Available</th>
                  <th>Missing</th>
                </tr>
              </thead>
              <tbody>
                {data.stock_gaps.map((g, i) => (
                  <tr key={i}>
                    <td>{g.product_name}</td>
                    <td>{g.needed}</td>
                    <td>{g.available}</td>
                    <td>{g.missing}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <PrintShell
        title={doc}
        meta={
          <>
            <div>Customer: {e.customer_name}</div>
            <div>Reg: {e.customer_reg_no}</div>
            <div>State: {e.approval_state}</div>
            <div>
              Final: {e.final_estimate} · Required advance: {e.required_advance}
            </div>
          </>
        }
      >
        <table className="print-table">
          <thead>
            <tr>
              <th>Line</th>
              <th>Qty/Hrs</th>
              <th>Price</th>
              <th>Approval</th>
            </tr>
          </thead>
          <tbody>
            {(e.items || []).map((i) => (
              <tr key={`i-${i.id}`}>
                <td>{i.product_name}</td>
                <td>{i.quantity}</td>
                <td>{i.line_total}</td>
                <td>{i.approval_status}</td>
              </tr>
            ))}
            {(e.labours || []).map((l) => (
              <tr key={`l-${l.id}`}>
                <td>{l.description}</td>
                <td>{l.std_hours ?? '—'}</td>
                <td>{l.price}</td>
                <td>{l.approval_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </PrintShell>
    </div>
  )
}

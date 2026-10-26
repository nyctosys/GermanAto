import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Loading, Money, NextActionBanner, PageHeader, Panel, StatusBadge } from '../components/ui'
import { PrintShell } from '../print/PrintShell'

type JobCard = {
  id: number
  customer_name?: string
  customer_phone?: string
  customer_reg_no?: string
  customer_made?: string
  status?: string
  visit_id?: number
  quote_invoice_id?: number
  lines?: Array<{
    id: number
    line_type: string
    description: string
    quantity: number
    unit_price: number
    pay_type: string
    line_status: string
    assigned_technician?: string
  }>
}

export function JobCardDetailPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const card = useQuery({
    queryKey: ['job-card', id],
    queryFn: () => api.get<JobCard>(`/api/job-cards/${id}`),
    enabled: !!id,
  })

  const quote = useMutation({
    mutationFn: () => api.post(`/api/job-cards/${id}/quote`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job-card', id] }),
  })

  const sendApproval = useMutation({
    mutationFn: (quoteId: number) =>
      api.post<{ approval_url: string }>(`/api/quotes/${quoteId}/send-approval`, {
        public_base_url: window.location.origin,
      }),
  })

  const next = useQuery({
    queryKey: ['next-action-jc', id],
    queryFn: () =>
      api.get<{ label: string; href?: string; code: string }>(
        `/api/pipeline/next-action?job_card_id=${id}`,
      ),
    enabled: !!id,
  })

  if (card.isLoading) return <Loading />
  if (card.error) return <ErrorBox error={card.error} />
  const row = card.data
  if (!row) return null

  return (
    <div>
      <PageHeader
        title={`Job card #${row.id}`}
        actions={
          <>
            <StatusBadge status={row.status || 'open'} tone="info" />
            {!row.quote_invoice_id ? (
              <button type="button" className="btn" onClick={() => quote.mutate()}>
                Build quotation
              </button>
            ) : (
              <>
                <Link className="btn btn-ghost" to={`/quotes/pending`}>
                  Quote #{row.quote_invoice_id}
                </Link>
                <button
                  type="button"
                  className="btn"
                  onClick={() => sendApproval.mutate(row.quote_invoice_id!)}
                >
                  Send WhatsApp approval
                </button>
              </>
            )}
          </>
        }
      />
      {next.data ? (
        <NextActionBanner label={next.data.label} href={next.data.href} hrefLabel="Go" />
      ) : null}
      {quote.error ? <ErrorBox error={quote.error} /> : null}
      {sendApproval.error ? <ErrorBox error={sendApproval.error} /> : null}
      {sendApproval.data ? (
        <p className="muted">
          Approval link: <a href={sendApproval.data.approval_url}>{sendApproval.data.approval_url}</a>
        </p>
      ) : null}
      <Panel title="Summary">
        <p>
          {row.customer_name} · {row.customer_phone} · {row.customer_reg_no} · {row.customer_made}
        </p>
        <p>
          Status: {row.status} · Visit: {row.visit_id || '—'}
        </p>
      </Panel>
      <PrintShell
        title={`Job card #${row.id}`}
        meta={
          <>
            <div>Customer: {row.customer_name}</div>
            <div>Reg: {row.customer_reg_no}</div>
            <div>Phone: {row.customer_phone}</div>
            <div>Status: {row.status}</div>
          </>
        }
      >
        <table className="print-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Pay</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(row.lines || []).map((ln) => (
              <tr key={ln.id}>
                <td>{ln.line_type}</td>
                <td>{ln.description}</td>
                <td>{ln.quantity}</td>
                <td>
                  <Money value={ln.unit_price} />
                </td>
                <td>{ln.pay_type}</td>
                <td>{ln.line_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </PrintShell>
    </div>
  )
}

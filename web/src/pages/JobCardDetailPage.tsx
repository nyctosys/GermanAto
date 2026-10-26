import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { AssignmentPanel } from '../components/AssignmentPanel'
import {
  ErrorBox,
  Field,
  Loading,
  Money,
  NextActionBanner,
  PageHeader,
  Panel,
  StatusBadge,
} from '../components/ui'
import { PrintShell } from '../print/PrintShell'

type JobCard = {
  id: number
  document_no?: string
  customer_name?: string
  customer_phone?: string
  customer_reg_no?: string
  customer_made?: string
  customer_id?: number
  car_id?: number
  status?: string
  priority?: string
  visit_id?: number
  quote_invoice_id?: number
  worker_id?: number
  worker_name?: string
  team_name?: string
  problem_description?: string
  inspection_notes?: string
  odometer?: string
  fuel_level?: string
  intake_at?: string
  expected_completion_at?: string
  notes?: string
  version?: number
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
  const nav = useNavigate()
  const [params] = useSearchParams()
  const justCreated = params.get('created') === '1'
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [assignOpen, setAssignOpen] = useState(justCreated)
  const [editForm, setEditForm] = useState<Partial<JobCard>>({})

  const card = useQuery({
    queryKey: ['job-card', id],
    queryFn: () => api.get<JobCard>(`/api/job-cards/${id}`),
    enabled: !!id,
  })

  const quote = useMutation({
    mutationFn: () => api.post<{ invoice_id: number }>(`/api/job-cards/${id}/quote`, {}),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['job-card', id] })
      if (res?.invoice_id) nav(`/quotes/${res.invoice_id}`)
    },
  })

  const sendApproval = useMutation({
    mutationFn: (quoteId: number) =>
      api.post<{ approval_url: string }>(`/api/quotes/${quoteId}/send-approval`, {
        public_base_url: window.location.origin,
      }),
  })

  const saveEdit = useMutation({
    mutationFn: () =>
      api.put(`/api/job-cards/${id}`, {
        ...editForm,
        version: card.data?.version,
        reason: 'Authorized job card edit',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['job-card', id] })
      setEditing(false)
    },
  })

  const openDraft = useMutation({
    mutationFn: () =>
      api.put(`/api/job-cards/${id}`, {
        status: 'open',
        version: card.data?.version,
        reason: 'Open draft job card',
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job-card', id] }),
  })

  const next = useQuery({
    queryKey: ['next-action-jc', id],
    queryFn: () =>
      api.get<{ label: string; href?: string; code: string }>(
        `/api/pipeline/next-action?job_card_id=${id}`,
      ),
    enabled: !!id,
  })

  const docNo = useMemo(
    () => card.data?.document_no || (card.data ? `JC-${String(card.data.id).padStart(5, '0')}` : ''),
    [card.data],
  )

  if (card.isLoading) return <Loading />
  if (card.error) return <ErrorBox error={card.error} />
  const row = card.data
  if (!row) return null

  function startEdit() {
    setEditForm({
      problem_description: row!.problem_description || '',
      inspection_notes: row!.inspection_notes || '',
      odometer: row!.odometer || '',
      fuel_level: row!.fuel_level || '',
      priority: row!.priority || 'normal',
      notes: row!.notes || '',
      team_name: row!.team_name || '',
      status: row!.status,
      expected_completion_at: row!.expected_completion_at || '',
    })
    setEditing(true)
  }

  return (
    <div>
      <PageHeader
        title={docNo}
        actions={
          <>
            <StatusBadge status={row.status || 'open'} tone="info" />
            <button type="button" className="btn btn-secondary" onClick={() => window.print()}>
              Print
            </button>
            {row.status === 'draft' ? (
              <button
                type="button"
                className="btn"
                disabled={openDraft.isPending}
                onClick={() => openDraft.mutate()}
              >
                Open job card
              </button>
            ) : null}
            {!row.quote_invoice_id && row.status !== 'draft' ? (
              <button type="button" className="btn" onClick={() => quote.mutate()}>
                Create estimate
              </button>
            ) : row.quote_invoice_id ? (
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
            ) : null}
            <button type="button" className="btn btn-secondary" onClick={() => setAssignOpen((v) => !v)}>
              Assign worker
            </button>
            <button type="button" className="btn btn-secondary" onClick={startEdit}>
              Edit
            </button>
          </>
        }
      />

      {justCreated ? (
        <Panel title="Next steps">
          <div className="row-actions">
            <button
              type="button"
              className="btn"
              disabled={!!row.quote_invoice_id || row.status === 'draft'}
              onClick={() => quote.mutate()}
            >
              Create estimate
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setAssignOpen(true)}>
              Assign worker
            </button>
            <Link className="btn btn-ghost" to={`/job-cards/${row.id}`}>
              View job
            </Link>
            {row.customer_id ? (
              <Link className="btn btn-ghost" to={`/customers/${row.customer_id}`}>
                Customer profile
              </Link>
            ) : null}
          </div>
        </Panel>
      ) : null}

      {next.data ? (
        <NextActionBanner label={next.data.label} href={next.data.href} hrefLabel="Go" />
      ) : null}
      {quote.error ? <ErrorBox error={quote.error} /> : null}
      {openDraft.error ? <ErrorBox error={openDraft.error} /> : null}
      {sendApproval.error ? <ErrorBox error={sendApproval.error} /> : null}
      {sendApproval.data ? (
        <p className="muted">
          Approval link:{' '}
          <a href={sendApproval.data.approval_url}>{sendApproval.data.approval_url}</a>
        </p>
      ) : null}

      {assignOpen ? (
        <AssignmentPanel
          jobCardId={row.id}
          version={row.version}
          defaultWorkerId={row.worker_id}
          defaultWorkerLabel={row.worker_name}
          defaultTeam={row.team_name}
          defaultPriority={row.priority || 'normal'}
          defaultDeadline={row.expected_completion_at}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ['job-card', id] })
            setAssignOpen(false)
          }}
        />
      ) : null}

      {editing ? (
        <Panel title="Edit intake (authorized)">
          {saveEdit.error ? <ErrorBox error={saveEdit.error} /> : null}
          <div className="form-grid">
            <Field label="Problem">
              <textarea
                className="input"
                rows={3}
                value={editForm.problem_description || ''}
                onChange={(e) => setEditForm({ ...editForm, problem_description: e.target.value })}
              />
            </Field>
            <Field label="Inspection notes">
              <textarea
                className="input"
                rows={3}
                value={editForm.inspection_notes || ''}
                onChange={(e) => setEditForm({ ...editForm, inspection_notes: e.target.value })}
              />
            </Field>
            <Field label="Odometer">
              <input
                className="input"
                value={editForm.odometer || ''}
                onChange={(e) => setEditForm({ ...editForm, odometer: e.target.value })}
              />
            </Field>
            <Field label="Fuel">
              <input
                className="input"
                value={editForm.fuel_level || ''}
                onChange={(e) => setEditForm({ ...editForm, fuel_level: e.target.value })}
              />
            </Field>
            <Field label="Priority">
              <select
                className="select"
                value={editForm.priority || 'normal'}
                onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </Field>
            <Field label="Status">
              <select
                className="select"
                value={editForm.status || 'open'}
                onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
              >
                <option value="draft">Draft</option>
                <option value="open">Open</option>
                <option value="quoted">Quoted</option>
                <option value="closed">Closed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </Field>
            <Field label="Notes">
              <textarea
                className="input"
                rows={2}
                value={editForm.notes || ''}
                onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
              />
            </Field>
            <button type="button" className="btn" disabled={saveEdit.isPending} onClick={() => saveEdit.mutate()}>
              Save changes
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
          {row.visit_id ? (
            <p className="muted" style={{ marginTop: 8 }}>
              Inspection photos:{' '}
              <Link to={row.car_id ? `/cars/${row.car_id}?tab=checkin` : '/cars'}>
                update visit #{row.visit_id}
              </Link>
            </p>
          ) : null}
        </Panel>
      ) : null}

      <Panel title="Summary">
        <p>
          {row.customer_name} · {row.customer_phone} · {row.customer_reg_no} · {row.customer_made}
        </p>
        <p>
          Priority: {row.priority || 'normal'} · Worker: {row.worker_name || '—'}
          {row.team_name ? ` · Team: ${row.team_name}` : ''}
        </p>
        <p>
          Intake: {row.intake_at || '—'} · Due: {row.expected_completion_at || '—'} · Visit:{' '}
          {row.visit_id || '—'}
        </p>
        <p>Odometer: {row.odometer || '—'} · Fuel: {row.fuel_level || '—'}</p>
        {row.problem_description ? <p>Problem: {row.problem_description}</p> : null}
        {row.inspection_notes ? <p>Inspection: {row.inspection_notes}</p> : null}
      </Panel>

      <PrintShell
        title={docNo}
        meta={
          <>
            <div>Customer: {row.customer_name}</div>
            <div>Reg: {row.customer_reg_no}</div>
            <div>Phone: {row.customer_phone}</div>
            <div>Status: {row.status}</div>
            <div>Priority: {row.priority}</div>
            <div>Problem: {row.problem_description}</div>
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

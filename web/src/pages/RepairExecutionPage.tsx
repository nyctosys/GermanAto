import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import {
  JobSummary,
  RepairJobFlow,
  friendlyDate,
  friendlyStatus,
} from '../components/RepairJobFlow'
import { ErrorBox, Field, Loading, Money, Panel } from '../components/ui'

type LabourLine = {
  id: number
  description: string
  status: string
  approval_status?: string
  std_hours?: number | null
  actual_hours?: number
  labour_rate?: number
  labour_cost?: number
  deadline_at?: string | null
  line_notes?: string | null
  clock_running?: boolean
  open_clock_started_at?: string | null
  is_done?: boolean
  workable?: boolean
  from_variation_id?: number | null
  labour_code?: string | null
}

/** Parse technician hour input: "1.5", "1,5", "0.25". */
function parseHoursInput(raw: string): number | null {
  const cleaned = raw.trim().replace(',', '.')
  if (!cleaned) return null
  const n = Number(cleaned)
  if (!Number.isFinite(n) || n <= 0) return null
  return Math.round(n * 10000) / 10000
}

function formatElapsed(startedAt?: string | null): string {
  if (!startedAt) return ''
  const normalized = startedAt.includes('T') ? startedAt : startedAt.replace(' ', 'T')
  const withTz = /Z|[+-]\d{2}:?\d{2}$/.test(normalized) ? normalized : `${normalized}Z`
  const start = new Date(withTz)
  if (Number.isNaN(start.getTime())) return ''
  const mins = Math.max(0, Math.floor((Date.now() - start.getTime()) / 60000))
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h <= 0) return `${m}m`
  return `${h}h ${m}m`
}

type PartLine = {
  id: number
  description: string
  part_number?: string | null
  quantity: number
  qty_issued: number
  qty_returned: number
  qty_remaining_to_issue: number
  qty_returnable: number
  status: string
  approval_status?: string
  ownership_type?: string
  unit_cost?: number
}

type ExecBoard = {
  repair_order: {
    id: number
    customer_name?: string
    customer_phone?: string
    customer_reg_no?: string
    customer_made?: string
    customer_mileage?: string
    customer_vin?: string | null
    customer_color?: string | null
    problem_description?: string | null
    diagnosis_plan?: string | null
    notes?: string | null
    current_status?: string
    worker_name?: string | null
    due_at?: string | null
    labour_cost_total?: number
    parts_cost_total?: number
    job_cost_total?: number
    submitted_for_qc_at?: string | null
  }
  progress?: { labour_done: number; labour_total: number; pct: number }
  labour: LabourLine[]
  parts: PartLine[]
  faults: Array<{
    id: number
    description: string
    status: string
    severity?: string
    variation_id?: number | null
    estimated_price?: number
    variation_status?: string | null
    editable?: boolean
    deletable?: boolean
    can_send?: boolean
    can_promote?: boolean
    added_to_job?: boolean
    approval_url?: string | null
    quote_invoice_id?: number | null
  }>
  variations: Array<{ id: number; status: string }>
  attachments: Array<{ id: number; file_path: string; original_name?: string }>
  next_action?: { label: string; href?: string }
  payroll_note?: string
}

function absoluteApprovalUrl(pathOrUrl?: string | null): string | null {
  if (!pathOrUrl) return null
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl
  return `${window.location.origin}${pathOrUrl.startsWith('/') ? '' : '/'}${pathOrUrl}`
}

function faultStatusLabel(f: {
  status: string
  variation_status?: string | null
  added_to_job?: boolean
}): string {
  const st = (f.status || '').toLowerCase()
  if (f.added_to_job || st === 'added' || st === 'promoted') return 'Added'
  const vs = (f.variation_status || '').toLowerCase()
  if (vs === 'draft') return 'Draft'
  if (vs === 'sent') return 'Sent to customer'
  if (vs === 'approved') return 'Approved'
  if (vs === 'partially_approved') return 'Partly approved'
  if (vs === 'rejected') return 'Rejected'
  if (st === 'cancelled') return 'Cancelled'
  return friendlyStatus(f.status) !== f.status ? friendlyStatus(f.status) : f.status
}

function faultPillClass(f: {
  status: string
  variation_status?: string | null
  added_to_job?: boolean
}): string {
  const label = faultStatusLabel(f)
  if (label === 'Added') return 'status-pill is-done'
  if (label === 'Approved' || label === 'Partly approved') return 'status-pill is-ready'
  if (label === 'Rejected' || label === 'Cancelled') return 'status-pill is-danger'
  return 'status-pill is-progress'
}

export function RepairExecutionPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { confirm, prompt } = useConfirm()
  const [faultDesc, setFaultDesc] = useState('')
  const [faultPrice, setFaultPrice] = useState('0')
  const [editingFaultId, setEditingFaultId] = useState<number | null>(null)
  const [editDesc, setEditDesc] = useState('')
  const [editPrice, setEditPrice] = useState('0')
  const [manualHours, setManualHours] = useState<Record<number, string>>({})
  const [hoursError, setHoursError] = useState<Record<number, string>>({})
  const [roNotes, setRoNotes] = useState<string | null>(null)
  const [partQty, setPartQty] = useState<Record<number, string>>({})
  const [reqDesc, setReqDesc] = useState('')
  const [reqQty, setReqQty] = useState('1')
  const [reqInvId, setReqInvId] = useState('')
  const [copiedFaultId, setCopiedFaultId] = useState<number | null>(null)
  const [expandedFaultId, setExpandedFaultId] = useState<number | null>(null)
  const [, setTick] = useState(0)

  const board = useQuery({
    queryKey: ['ro-execution', id],
    queryFn: () => api.get<ExecBoard>(`/api/repair-orders/${id}/execution`),
    enabled: !!id,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['ro-execution', id] })

  useEffect(() => {
    const running = board.data?.labour?.some((l) => l.clock_running)
    if (!running) return
    const t = window.setInterval(() => setTick((n) => n + 1), 30000)
    return () => window.clearInterval(t)
  }, [board.data?.labour])

  const startM = useMutation({
    mutationFn: (labourId: number) =>
      api.post(`/api/repair-orders/${id}/execution/labour/${labourId}/start`, {}),
    onSuccess: invalidate,
  })
  const pauseM = useMutation({
    mutationFn: (labourId: number) =>
      api.post(`/api/repair-orders/${id}/execution/labour/${labourId}/pause`, {}),
    onSuccess: invalidate,
  })
  const resumeM = useMutation({
    mutationFn: (labourId: number) =>
      api.post(`/api/repair-orders/${id}/execution/labour/${labourId}/resume`, {}),
    onSuccess: invalidate,
  })
  const timeM = useMutation({
    mutationFn: ({
      labourId,
      hours,
      replace,
    }: {
      labourId: number
      hours: number
      replace?: boolean
    }) =>
      api.post(`/api/repair-orders/${id}/execution/labour/${labourId}/time`, {
        hours,
        replace: !!replace,
      }),
    onSuccess: (_data, vars) => {
      setManualHours((s) => ({ ...s, [vars.labourId]: '' }))
      setHoursError((s) => {
        const next = { ...s }
        delete next[vars.labourId]
        return next
      })
      invalidate()
    },
  })
  const doneM = useMutation({
    mutationFn: (labourId: number) =>
      api.post(`/api/repair-orders/${id}/execution/labour/${labourId}/complete`, {}),
    onSuccess: invalidate,
  })

  const clockBusy =
    startM.isPending || pauseM.isPending || resumeM.isPending || timeM.isPending || doneM.isPending

  function submitHours(lab: LabourLine, replace: boolean) {
    const parsed = parseHoursInput(manualHours[lab.id] || '')
    if (parsed == null) {
      setHoursError((s) => ({
        ...s,
        [lab.id]: replace ? 'Enter total hours (e.g. 1.5)' : 'Enter hours to add (e.g. 0.5)',
      }))
      return
    }
    if (!replace && parsed > 24) {
      setHoursError((s) => ({ ...s, [lab.id]: 'One entry cannot exceed 24 hours' }))
      return
    }
    if (replace && parsed > 100) {
      setHoursError((s) => ({ ...s, [lab.id]: 'Total cannot exceed 100 hours' }))
      return
    }
    setHoursError((s) => {
      const next = { ...s }
      delete next[lab.id]
      return next
    })
    timeM.mutate({ labourId: lab.id, hours: parsed, replace })
  }
  const [partActionError, setPartActionError] = useState<string | null>(null)
  const issueM = useMutation({
    mutationFn: ({ partId, qty }: { partId: number; qty?: number }) =>
      api.post(
        `/api/repair-orders/${id}/execution/parts/${partId}/issue`,
        qty != null ? { qty } : {},
        { reason: `Issue parts to RO #${id}` },
      ),
    onSuccess: (_data, vars) => {
      setPartQty((s) => {
        const next = { ...s }
        delete next[vars.partId]
        return next
      })
      setPartActionError(null)
      invalidate()
    },
  })
  const returnM = useMutation({
    mutationFn: ({ partId, qty }: { partId: number; qty?: number }) =>
      api.post(
        `/api/repair-orders/${id}/execution/parts/${partId}/return`,
        qty != null ? { qty } : {},
        { reason: `Return unused parts from RO #${id}` },
      ),
    onSuccess: (_data, vars) => {
      setPartQty((s) => {
        const next = { ...s }
        delete next[vars.partId]
        return next
      })
      setPartActionError(null)
      invalidate()
    },
  })

  function parsePartQty(raw: string): number | null {
    const cleaned = raw.trim()
    if (!cleaned) return null
    const n = Number(cleaned)
    if (!Number.isFinite(n) || !Number.isInteger(n) || n <= 0) return null
    return n
  }

  function runIssue(p: PartLine) {
    setPartActionError(null)
    const raw = partQty[p.id] || ''
    const parsed = parsePartQty(raw)
    if (raw.trim() && parsed == null) {
      setPartActionError('Enter a whole number qty to issue')
      return
    }
    const amount = parsed ?? p.qty_remaining_to_issue
    if (amount > p.qty_remaining_to_issue) {
      setPartActionError(
        `Cannot issue ${amount}: only ${p.qty_remaining_to_issue} remaining for ${p.description}`,
      )
      return
    }
    issueM.mutate({ partId: p.id, qty: parsed ?? undefined })
  }

  function runReturn(p: PartLine) {
    setPartActionError(null)
    const raw = partQty[p.id] || ''
    const parsed = parsePartQty(raw)
    if (raw.trim() && parsed == null) {
      setPartActionError('Enter a whole number qty to return')
      return
    }
    const amount = parsed ?? p.qty_returnable
    if (amount > p.qty_returnable) {
      setPartActionError(
        `Cannot return ${amount}: only ${p.qty_returnable} returnable for ${p.description}`,
      )
      return
    }
    returnM.mutate({ partId: p.id, qty: parsed ?? undefined })
  }
  const faultM = useMutation({
    mutationFn: () =>
      api.post(`/api/repair-orders/${id}/execution/faults`, {
        description: faultDesc,
        estimated_price: Number(faultPrice) || 0,
      }),
    onSuccess: () => {
      setFaultDesc('')
      setFaultPrice('0')
      invalidate()
    },
  })
  const updateFaultM = useMutation({
    mutationFn: ({
      faultId,
      description,
      estimated_price,
    }: {
      faultId: number
      description: string
      estimated_price: number
    }) =>
      api.patch(`/api/repair-orders/${id}/execution/faults/${faultId}`, {
        description,
        estimated_price,
      }),
    onSuccess: () => {
      setEditingFaultId(null)
      invalidate()
    },
  })
  const deleteFaultM = useMutation({
    mutationFn: (faultId: number) =>
      api.delete(`/api/repair-orders/${id}/execution/faults/${faultId}`),
    onSuccess: invalidate,
  })
  const sendVarM = useMutation({
    mutationFn: (varId: number) =>
      api.post<{ approval_url?: string; invoice_id?: number }>(`/api/variations/${varId}/send`, {
        public_base_url: window.location.origin,
      }),
    onSuccess: invalidate,
  })

  async function copyLink(faultId: number, url: string) {
    try {
      await navigator.clipboard.writeText(url)
      setCopiedFaultId(faultId)
      window.setTimeout(() => setCopiedFaultId((cur) => (cur === faultId ? null : cur)), 2000)
    } catch {
      void prompt({ title: 'Copy link', message: 'Copy this link:', defaultValue: url, confirmLabel: 'OK', required: false })
    }
  }
  const promoteM = useMutation({
    mutationFn: (varId: number) =>
      api.post(`/api/repair-orders/${id}/execution/variations/${varId}/promote`, {}),
    onSuccess: invalidate,
  })
  const notesM = useMutation({
    mutationFn: (notes: string) =>
      api.post(`/api/repair-orders/${id}/execution/notes`, { notes }),
    onSuccess: invalidate,
  })
  const requestPartsM = useMutation({
    mutationFn: () =>
      api.post(`/api/repair-orders/${id}/execution/parts/request`, {
        description: reqDesc,
        quantity: Number(reqQty) || 1,
        inventory_id: reqInvId ? Number(reqInvId) : null,
        bill_customer: false,
      }),
    onSuccess: () => {
      setReqDesc('')
      setReqInvId('')
      invalidate()
    },
  })
  const submitM = useMutation({
    mutationFn: () => api.post(`/api/repair-orders/${id}/execution/submit-inspection`, {}),
    onSuccess: invalidate,
  })
  const uploadM = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return api.post(`/api/repair-orders/${id}/execution/attachments`, fd)
    },
    onSuccess: invalidate,
  })

  if (board.isLoading) return <Loading />
  if (board.error) return <ErrorBox error={board.error} />
  const data = board.data
  if (!data) return <p className="muted">No execution data</p>

  const ro = data.repair_order

  return (
    <div>
      <RepairJobFlow
        roId={ro.id}
        step="work"
        vehicleLabel={`${ro.customer_made || ''} ${ro.customer_reg_no || ''}`.trim()}
      />

      <JobSummary
        jobId={ro.id}
        vehicle={ro.customer_made}
        regNo={ro.customer_reg_no}
        customerName={ro.customer_name}
        customerPhone={ro.customer_phone}
        mileage={ro.customer_mileage}
        vin={ro.customer_vin}
        color={ro.customer_color}
        status={ro.current_status}
        technician={ro.worker_name}
        dueAt={ro.due_at}
        labourDone={data.progress?.labour_done}
        labourTotal={data.progress?.labour_total}
        labourCost={ro.labour_cost_total}
        partsCost={ro.parts_cost_total}
        jobCost={ro.job_cost_total}
        complaint={ro.problem_description}
        plan={ro.diagnosis_plan}
      />

      <Panel title="Approved tasks">
        {[startM, pauseM, resumeM, timeM, doneM].map((m, i) =>
          m.error ? <ErrorBox key={i} error={m.error} /> : null,
        )}
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Task</th>
                <th>Status</th>
                <th>Hours</th>
                <th>Rate / cost</th>
                <th>Deadline</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.labour.map((lab) => {
                const blocked =
                  !!lab.from_variation_id &&
                  (lab.approval_status || '').toLowerCase() !== 'approved'
                const done = lab.is_done || (lab.status || '').toLowerCase() === 'done'
                const st = (lab.status || '').toLowerCase()
                const canWork = !blocked && !done
                const elapsed = lab.clock_running
                  ? formatElapsed(lab.open_clock_started_at)
                  : ''
                return (
                  <tr key={lab.id}>
                    <td>
                      {lab.labour_code ? <span className="muted">{lab.labour_code} · </span> : null}
                      {lab.description}
                      {blocked ? (
                        <div className="muted">Awaiting customer approval</div>
                      ) : null}
                      {lab.line_notes ? <div className="muted">{lab.line_notes}</div> : null}
                    </td>
                    <td>
                      {lab.status}
                      {lab.clock_running ? (
                        <div className="muted">Clocking{elapsed ? ` · ${elapsed}` : ''}</div>
                      ) : null}
                    </td>
                    <td>
                      std {lab.std_hours ?? '—'} / actual {(lab.actual_hours || 0).toFixed(2)}
                    </td>
                    <td>
                      <Money value={lab.labour_rate || 0} /> /h →{' '}
                      <Money value={lab.labour_cost || 0} />
                    </td>
                    <td>{friendlyDate(lab.deadline_at)}</td>
                    <td>
                      {canWork ? (
                        <div className="task-time-actions">
                          <div className="row-actions">
                            {lab.clock_running ? (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                disabled={clockBusy}
                                onClick={() => pauseM.mutate(lab.id)}
                              >
                                Pause
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-sm"
                                disabled={clockBusy}
                                onClick={() =>
                                  st === 'paused'
                                    ? resumeM.mutate(lab.id)
                                    : startM.mutate(lab.id)
                                }
                              >
                                {st === 'paused' ? 'Resume' : 'Start'}
                              </button>
                            )}
                            <input
                              className="input"
                              style={{ width: '4.5rem' }}
                              inputMode="decimal"
                              placeholder="hrs"
                              aria-label={`Hours for ${lab.description}`}
                              value={manualHours[lab.id] || ''}
                              disabled={clockBusy}
                              onChange={(e) => {
                                const v = e.target.value
                                setManualHours((s) => ({ ...s, [lab.id]: v }))
                                if (hoursError[lab.id]) {
                                  setHoursError((s) => {
                                    const next = { ...s }
                                    delete next[lab.id]
                                    return next
                                  })
                                }
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault()
                                  submitHours(lab, false)
                                }
                              }}
                            />
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={clockBusy}
                              title="Add these hours to the total (pauses clock if running)"
                              onClick={() => submitHours(lab, false)}
                            >
                              Add hours
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              disabled={clockBusy}
                              title="Replace actual hours with this total"
                              onClick={() => submitHours(lab, true)}
                            >
                              Set total
                            </button>
                            <button
                              type="button"
                              className="btn btn-sm"
                              disabled={clockBusy}
                              onClick={() => doneM.mutate(lab.id)}
                            >
                              Complete
                            </button>
                          </div>
                          {hoursError[lab.id] ? (
                            <div className="field-error">{hoursError[lab.id]}</div>
                          ) : null}
                          {lab.clock_running ? (
                            <div className="muted" style={{ fontSize: '0.8rem' }}>
                              Adding hours will pause the clock first
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Required parts">
        {[issueM, returnM, requestPartsM].map((m, i) =>
          m.error ? <ErrorBox key={i} error={m.error} /> : null,
        )}
        {partActionError ? <div className="field-error">{partActionError}</div> : null}
        <div className="form-grid" style={{ marginBottom: '0.75rem' }}>
          <Field label="Request internal part (description)">
            <input className="input" value={reqDesc} onChange={(e) => setReqDesc(e.target.value)} />
          </Field>
          <Field label="Inventory id (optional)">
            <input className="input" value={reqInvId} onChange={(e) => setReqInvId(e.target.value)} />
          </Field>
          <Field label="Qty">
            <input className="input" value={reqQty} onChange={(e) => setReqQty(e.target.value)} />
          </Field>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!reqDesc.trim() || requestPartsM.isPending}
          onClick={() => requestPartsM.mutate()}
        >
          Request shop parts
        </button>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Part</th>
                <th>Qty</th>
                <th>Issued / returned</th>
                <th>Unit cost</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.parts.map((p) => {
                const canIssue =
                  p.qty_remaining_to_issue > 0 && p.ownership_type !== 'customer_supplied'
                const canReturn = p.qty_returnable > 0
                const showQty = canIssue || canReturn
                return (
                  <tr key={p.id}>
                    <td>
                      {p.description}
                      {p.part_number ? <div className="muted">{p.part_number}</div> : null}
                    </td>
                    <td>{p.quantity}</td>
                    <td>
                      {p.qty_issued} / {p.qty_returned}
                    </td>
                    <td>
                      <Money value={p.unit_cost || 0} />
                    </td>
                    <td>{p.status}</td>
                    <td className="row-actions">
                      {showQty ? (
                        <input
                          className="input"
                          style={{ width: '3.5rem' }}
                          inputMode="numeric"
                          placeholder="qty"
                          aria-label={`Qty for ${p.description}`}
                          value={partQty[p.id] || ''}
                          disabled={issueM.isPending || returnM.isPending}
                          onChange={(e) => {
                            setPartQty((s) => ({ ...s, [p.id]: e.target.value }))
                            if (partActionError) setPartActionError(null)
                          }}
                        />
                      ) : (
                        <span className="muted">—</span>
                      )}
                      {canIssue ? (
                        <button
                          type="button"
                          className="btn btn-sm"
                          disabled={issueM.isPending || returnM.isPending}
                          title={
                            partQty[p.id]?.trim()
                              ? `Issue ${partQty[p.id]} (max ${p.qty_remaining_to_issue})`
                              : `Issue remaining ${p.qty_remaining_to_issue}`
                          }
                          onClick={() => runIssue(p)}
                        >
                          Issue
                        </button>
                      ) : null}
                      {canReturn ? (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={issueM.isPending || returnM.isPending}
                          title={
                            partQty[p.id]?.trim()
                              ? `Return ${partQty[p.id]} (max ${p.qty_returnable})`
                              : `Return unused ${p.qty_returnable}`
                          }
                          onClick={() => runReturn(p)}
                        >
                          Return unused
                        </button>
                      ) : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Additional faults">
        {[faultM, updateFaultM, deleteFaultM, sendVarM, promoteM].map((m, i) =>
          m.error ? <ErrorBox key={i} error={m.error} /> : null,
        )}
        <div className="form-grid fault-add-form">
          <Field label="Fault description">
            <input
              className="input"
              value={faultDesc}
              onChange={(e) => setFaultDesc(e.target.value)}
              placeholder="What extra problem did you find?"
            />
          </Field>
          <Field label="Estimated price (PKR)">
            <input
              className="input"
              value={faultPrice}
              onChange={(e) => setFaultPrice(e.target.value)}
            />
          </Field>
        </div>
        <button
          type="button"
          className="btn"
          disabled={!faultDesc.trim() || faultM.isPending}
          onClick={() => faultM.mutate()}
        >
          Add fault
        </button>

        {data.faults.length === 0 ? (
          <p className="muted" style={{ marginTop: '0.75rem' }}>
            No extra faults yet.
          </p>
        ) : (
          <div className="table-wrap" style={{ marginTop: '1rem' }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Fault</th>
                  <th>Price</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.faults.map((f) => {
                  const editing = editingFaultId === f.id
                  const expanded = expandedFaultId === f.id
                  const link =
                    absoluteApprovalUrl(f.approval_url) ||
                    (sendVarM.data?.approval_url &&
                    sendVarM.variables === f.variation_id
                      ? absoluteApprovalUrl(sendVarM.data.approval_url)
                      : null)
                  return (
                    <Fragment key={f.id}>
                      <tr
                        className={`fault-row${expanded ? ' is-expanded' : ''}${link ? ' is-clickable' : ''}`}
                        onClick={async () => {
                          if (editing || !link) return
                          setExpandedFaultId((cur) => (cur === f.id ? null : f.id))
                        }}
                      >
                        <td>
                          {editing ? (
                            <input
                              className="input"
                              value={editDesc}
                              onChange={(e) => setEditDesc(e.target.value)}
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <>
                              <strong>#{f.id}</strong> {f.description}
                            </>
                          )}
                        </td>
                        <td>
                          {editing ? (
                            <input
                              className="input"
                              style={{ width: '6rem' }}
                              value={editPrice}
                              onChange={(e) => setEditPrice(e.target.value)}
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <Money value={f.estimated_price || 0} />
                          )}
                        </td>
                        <td>
                          <span className={faultPillClass(f)}>{faultStatusLabel(f)}</span>
                        </td>
                        <td
                          className="row-actions"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {editing ? (
                            <>
                              <button
                                type="button"
                                className="btn btn-sm"
                                disabled={!editDesc.trim() || updateFaultM.isPending}
                                onClick={() =>
                                  updateFaultM.mutate({
                                    faultId: f.id,
                                    description: editDesc,
                                    estimated_price: Number(editPrice) || 0,
                                  })
                                }
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => setEditingFaultId(null)}
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              {f.editable ? (
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => {
                                    setEditingFaultId(f.id)
                                    setEditDesc(f.description)
                                    setEditPrice(String(f.estimated_price ?? 0))
                                  }}
                                >
                                  Edit
                                </button>
                              ) : null}
                              {f.can_send && f.variation_id ? (
                                <button
                                  type="button"
                                  className="btn btn-sm"
                                  disabled={sendVarM.isPending}
                                  onClick={() => {
                                    sendVarM.mutate(f.variation_id!)
                                    setExpandedFaultId(f.id)
                                  }}
                                >
                                  Send
                                </button>
                              ) : null}
                              {f.can_promote && f.variation_id ? (
                                <button
                                  type="button"
                                  className="btn btn-sm"
                                  disabled={promoteM.isPending}
                                  onClick={() => promoteM.mutate(f.variation_id!)}
                                >
                                  Add to job
                                </button>
                              ) : null}
                              {f.deletable ? (
                                <button
                                  type="button"
                                  className="btn btn-danger btn-sm"
                                  disabled={deleteFaultM.isPending}
                                  onClick={async () => {
                                    if (await confirm({ message: `Delete fault #${f.id}?`, danger: true, confirmLabel: 'Delete' }))
                                      deleteFaultM.mutate(f.id)
                                  }}
                                >
                                  Delete
                                </button>
                              ) : null}
                            </>
                          )}
                        </td>
                      </tr>
                      {expanded && link ? (
                        <tr className="fault-link-row">
                          <td colSpan={4}>
                            <div className="fault-approval-link">
                              <span className="muted">Customer link:</span>
                              <a href={link} target="_blank" rel="noreferrer" className="fault-link-url">
                                {link}
                              </a>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => copyLink(f.id, link)}
                              >
                                {copiedFaultId === f.id ? 'Copied' : 'Copy'}
                              </button>
                              <a className="btn btn-sm" href={link} target="_blank" rel="noreferrer">
                                Open
                              </a>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Notes & photos">
        {notesM.error || uploadM.error ? (
          <ErrorBox error={notesM.error || uploadM.error} />
        ) : null}
        <Field label="Job notes">
          <textarea
            className="input"
            rows={3}
            value={roNotes ?? ro.notes ?? ''}
            onChange={(e) => setRoNotes(e.target.value)}
          />
        </Field>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => notesM.mutate(roNotes ?? ro.notes ?? '')}
        >
          Save notes
        </button>
        <div style={{ marginTop: '0.75rem' }}>
          <input
            type="file"
            accept="image/*,application/pdf"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) uploadM.mutate(f)
            }}
          />
        </div>
        <ul>
          {data.attachments.map((a) => (
            <li key={a.id}>
              <a href={`/${a.file_path}`} target="_blank" rel="noreferrer">
                {a.original_name || a.file_path}
              </a>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Submit for inspection">
        {submitM.error ? <ErrorBox error={submitM.error} /> : null}
        {ro.submitted_for_qc_at ? (
          <p className="status-pill is-ready">Submitted {friendlyDate(ro.submitted_for_qc_at)}</p>
        ) : (
          <button type="button" className="btn" onClick={() => submitM.mutate()}>
            Submit for inspection
          </button>
        )}
      </Panel>
    </div>
  )
}

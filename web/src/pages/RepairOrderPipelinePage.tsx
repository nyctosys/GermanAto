import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import { JobSummary, RepairJobFlow } from '../components/RepairJobFlow'
import { ErrorBox, Field, Loading, Panel } from '../components/ui'
import { PrintShell } from '../print/PrintShell'

export function RepairOrderPipelinePage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [qcNote, setQcNote] = useState('')
  const [exitOdo, setExitOdo] = useState('')
  const [bypass, setBypass] = useState(false)
  const [reason, setReason] = useState('')
  const [varDesc, setVarDesc] = useState('')
  const [varPrice, setVarPrice] = useState('0')
  const [displayTitle, setDisplayTitle] = useState('')

  const roDetail = useQuery({
    queryKey: ['ro-detail', id],
    queryFn: () =>
      api.get<{
        id: number
        document_no?: string
        display_title?: string
        version?: number
      }>(`/api/repair-orders/${id}`),
    enabled: !!id,
  })

  const rename = useMutation({
    mutationFn: () =>
      api.post(`/api/repair-orders/${id}/rename`, {
        display_title: displayTitle,
        version: roDetail.data?.version,
        reason: reason || 'Repair order rename',
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ro-detail', id] }),
  })

  const qcQ = useQuery({
    queryKey: ['ro-qc', id],
    queryFn: () => api.get<{ qc: Record<string, unknown> | null }>(`/api/repair-orders/${id}/qc`),
    enabled: !!id,
  })
  const gateQ = useQuery({
    queryKey: ['ro-gate', id],
    queryFn: () =>
      api.get<{ gate_pass: Record<string, unknown> | null }>(`/api/repair-orders/${id}/gate-pass`),
    enabled: !!id,
  })
  const varsQ = useQuery({
    queryKey: ['ro-vars', id],
    queryFn: () => api.get<Array<{ id: number; status: string }>>(`/api/repair-orders/${id}/variations`),
    enabled: !!id,
  })
  const execQ = useQuery({
    queryKey: ['ro-execution-lite', id],
    queryFn: () =>
      api.get<{
        repair_order: {
          id: number
          customer_made?: string
          customer_reg_no?: string
          customer_name?: string
          customer_phone?: string
          customer_mileage?: string
          customer_vin?: string | null
          customer_color?: string | null
          current_status?: string
          worker_name?: string | null
          due_at?: string | null
          labour_cost_total?: number
          parts_cost_total?: number
          job_cost_total?: number
          problem_description?: string | null
          diagnosis_plan?: string | null
        }
        progress?: { labour_done: number; labour_total: number }
      }>(`/api/repair-orders/${id}/execution`),
    enabled: !!id,
  })

  const postQc = useMutation({
    mutationFn: () =>
      api.post(
        `/api/repair-orders/${id}/qc`,
        {
          checklist: [{ key: 'work_done', label: 'Work completed to standard', ok: true }],
          road_test_note: qcNote,
          photos: [],
          reason: reason || 'QC sign-off',
        },
        { reason: reason || 'QC sign-off' },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ro-qc', id] }),
  })

  const postGate = useMutation({
    mutationFn: () =>
      api.post(
        `/api/repair-orders/${id}/gate-pass`,
        {
          old_parts_checklist: [{ item: 'Old parts returned', done: true }],
          exit_odometer: exitOdo,
          photos: [],
          payment_gate_bypass: bypass,
          reason: reason || undefined,
        },
        { reason: bypass ? reason : undefined },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ro-gate', id] }),
  })

  const createVar = useMutation({
    mutationFn: () =>
      api.post(`/api/repair-orders/${id}/variations`, {
        notes: 'Extra work',
        lines: [{ line_type: 'labour', description: varDesc, quantity: 1, unit_price: Number(varPrice) }],
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ro-vars', id] })
      setVarDesc('')
    },
  })

  const sendVar = useMutation({
    mutationFn: (vid: number) =>
      api.post(`/api/variations/${vid}/send`, { public_base_url: window.location.origin }),
  })

  if (qcQ.isLoading) return <Loading />

  const ro = execQ.data?.repair_order
  const hasQc = Boolean(qcQ.data?.qc)
  const hasGate = Boolean(gateQ.data?.gate_pass)
  const step = hasGate || hasQc ? 'handover' : 'check'
  const docLabel =
    roDetail.data?.display_title ||
    roDetail.data?.document_no ||
    (id ? `RO-${String(id).padStart(5, '0')}` : 'RO')

  return (
    <div>
      <RepairJobFlow
        roId={id || ''}
        step={step}
        vehicleLabel={
          ro ? `${ro.customer_made || ''} ${ro.customer_reg_no || ''}`.trim() : undefined
        }
      />

      {ro ? (
        <JobSummary
          jobId={ro.id || id || ''}
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
          labourDone={execQ.data?.progress?.labour_done}
          labourTotal={execQ.data?.progress?.labour_total}
          labourCost={ro.labour_cost_total}
          partsCost={ro.parts_cost_total}
          jobCost={ro.job_cost_total}
          complaint={ro.problem_description}
          plan={ro.diagnosis_plan}
        />
      ) : (
        <h1 style={{ marginBottom: 16 }}>{docLabel}</h1>
      )}

      <Panel title="Rename (keeps original document no)">
        {rename.error ? <ErrorBox error={rename.error} /> : null}
        <p className="muted">
          Permanent reference: {roDetail.data?.document_no || `RO-${id}`} · History and links stay on
          this ID.
        </p>
        <div className="form-grid">
          <Field label="Display title">
            <input
              className="input"
              value={displayTitle || roDetail.data?.display_title || ''}
              onChange={(e) => setDisplayTitle(e.target.value)}
              placeholder="e.g. Civic AC job — Ali"
            />
          </Field>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={rename.isPending}
            onClick={() => rename.mutate()}
          >
            Save title
          </button>
        </div>
      </Panel>

      <Panel title="Quality check">
        {postQc.error ? <ErrorBox error={postQc.error} /> : null}
        {hasQc ? (
          <p className="status-pill is-ready">
            Signed by {(qcQ.data?.qc as { signed_by?: string }).signed_by}
          </p>
        ) : (
          <>
            <Field label="Road test note">
              <textarea
                className="input"
                rows={3}
                value={qcNote}
                onChange={(e) => setQcNote(e.target.value)}
              />
            </Field>
            <Field label="Reason">
              <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
            <button type="button" className="btn" onClick={() => postQc.mutate()}>
              Sign QC
            </button>
          </>
        )}
      </Panel>

      <Panel title="Extra work">
        {createVar.error ? <ErrorBox error={createVar.error} /> : null}
        <div className="form-grid">
          <Field label="Description">
            <input className="input" value={varDesc} onChange={(e) => setVarDesc(e.target.value)} />
          </Field>
          <Field label="Price (PKR)">
            <input className="input" value={varPrice} onChange={(e) => setVarPrice(e.target.value)} />
          </Field>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!varDesc.trim()}
          onClick={() => createVar.mutate()}
        >
          Save
        </button>
        <ul>
          {(varsQ.data || []).map((v) => (
            <li key={v.id}>
              #{v.id} — {v.status}{' '}
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => sendVar.mutate(v.id)}>
                Send
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <div id="handover" />
      <Panel title="Gate pass">
        {postGate.error ? <ErrorBox error={postGate.error} /> : null}
        {!hasQc ? (
          <p className="muted">QC required first.</p>
        ) : hasGate ? (
          <PrintShell title={`Gate pass RO #${id}`}>
            <p>Delivered.</p>
          </PrintShell>
        ) : (
          <>
            <Field label="Exit odometer">
              <input className="input" value={exitOdo} onChange={(e) => setExitOdo(e.target.value)} />
            </Field>
            <label className="field">
              <span>
                <input type="checkbox" checked={bypass} onChange={(e) => setBypass(e.target.checked)} />{' '}
                Bypass payment gate
              </span>
            </label>
            {bypass ? (
              <Field label="Override reason">
                <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
              </Field>
            ) : null}
            <button type="button" className="btn" onClick={() => postGate.mutate()}>
              Create gate pass
            </button>
          </>
        )}
      </Panel>
    </div>
  )
}

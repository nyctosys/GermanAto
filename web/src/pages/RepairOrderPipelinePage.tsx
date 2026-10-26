import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Field, Loading, NextActionBanner, PageHeader, Panel } from '../components/ui'
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

  const ro = useQuery({
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
        version: ro.data?.version,
        reason: reason || 'Repair order rename',
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ro-detail', id] }),
  })

  const next = useQuery({
    queryKey: ['next-action-ro', id],
    queryFn: () =>
      api.get<{ label: string; href?: string }>(`/api/pipeline/next-action?repair_order_id=${id}`),
    enabled: !!id,
  })
  const qcQ = useQuery({
    queryKey: ['ro-qc', id],
    queryFn: () => api.get<{ qc: Record<string, unknown> | null }>(`/api/repair-orders/${id}/qc`),
    enabled: !!id,
  })
  const gateQ = useQuery({
    queryKey: ['ro-gate', id],
    queryFn: () => api.get<{ gate_pass: Record<string, unknown> | null }>(`/api/repair-orders/${id}/gate-pass`),
    enabled: !!id,
  })
  const varsQ = useQuery({
    queryKey: ['ro-vars', id],
    queryFn: () => api.get<Array<{ id: number; status: string }>>(`/api/repair-orders/${id}/variations`),
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

  const docLabel =
    ro.data?.display_title ||
    ro.data?.document_no ||
    (id ? `RO-${String(id).padStart(5, '0')}` : 'RO')

  return (
    <div>
      <PageHeader title={`${docLabel} pipeline`} />
      {next.data ? (
        <NextActionBanner label={next.data.label} href={next.data.href} hrefLabel="Go" />
      ) : null}
      <Panel title="Rename (keeps original document no)">
        {rename.error ? <ErrorBox error={rename.error} /> : null}
        <p className="muted">
          Permanent reference: {ro.data?.document_no || `RO-${id}`} · History and links stay on this
          ID.
        </p>
        <div className="form-grid">
          <Field label="Display title">
            <input
              className="input"
              value={displayTitle || ro.data?.display_title || ''}
              onChange={(e) => setDisplayTitle(e.target.value)}
              placeholder="e.g. Civic AC job — Ali"
            />
          </Field>
          <button type="button" className="btn btn-secondary" disabled={rename.isPending} onClick={() => rename.mutate()}>
            Save title
          </button>
        </div>
      </Panel>
      <Panel title="QC sign-off">
        {postQc.error ? <ErrorBox error={postQc.error} /> : null}
        {qcQ.data?.qc ? (
          <p className="muted">Signed by {(qcQ.data.qc as { signed_by?: string }).signed_by}</p>
        ) : (
          <>
            <Field label="Road test note">
              <textarea className="input" value={qcNote} onChange={(e) => setQcNote(e.target.value)} />
            </Field>
            <Field label="Reason (audit)">
              <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
            </Field>
            <button type="button" className="btn" onClick={() => postQc.mutate()}>
              Sign QC
            </button>
          </>
        )}
      </Panel>
      <Panel title="Variations">
        {createVar.error ? <ErrorBox error={createVar.error} /> : null}
        <div className="form-grid">
          <Field label="Extra work description">
            <input className="input" value={varDesc} onChange={(e) => setVarDesc(e.target.value)} />
          </Field>
          <Field label="Price">
            <input className="input" value={varPrice} onChange={(e) => setVarPrice(e.target.value)} />
          </Field>
        </div>
        <button type="button" className="btn" onClick={() => createVar.mutate()}>
          Flag variation
        </button>
        <ul>
          {(varsQ.data || []).map((v) => (
            <li key={v.id}>
              Variation #{v.id} — {v.status}{' '}
              <button type="button" className="btn btn-ghost" onClick={() => sendVar.mutate(v.id)}>
                Send for approval
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Gate pass / handover">
        {postGate.error ? <ErrorBox error={postGate.error} /> : null}
        {gateQ.data?.gate_pass ? (
          <PrintShell title={`Gate pass RO #${id}`}>
            <p>Delivered. Exit odometer recorded.</p>
          </PrintShell>
        ) : (
          <>
            <Field label="Exit odometer">
              <input className="input" value={exitOdo} onChange={(e) => setExitOdo(e.target.value)} />
            </Field>
            <label className="field">
              <span>
                <input type="checkbox" checked={bypass} onChange={(e) => setBypass(e.target.checked)} /> Bypass payment
                gate
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

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Money } from '../components/ui'

type Line = {
  id: number
  kind: string
  product_name?: string
  description?: string
  quantity?: number
  price: number
  proposed_price?: number
  approval_status: string
}

type Payload = {
  invoice_id: number
  customer_name: string
  customer_reg_no: string
  net_total: number
  items: Line[]
  labours: Line[]
}

async function publicGet<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `HTTP ${res.status}`)
  }
  return res.json()
}

async function publicPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export function PublicApprovePage() {
  const { token } = useParams()
  const qc = useQueryClient()
  const [decisions, setDecisions] = useState<Record<string, string>>({})
  const [media, setMedia] = useState<Record<string, string>>({})

  const q = useQuery({
    queryKey: ['public-quote', token],
    queryFn: () => publicGet<Payload>(`/api/public/quotes/${token}`),
    enabled: !!token,
  })

  const lines = useMemo(() => {
    const payload = q.data
    if (!payload) return []
    return [
      ...payload.items.map((i) => ({ ...i, kind: 'item', label: i.product_name || '' })),
      ...payload.labours.map((l) => ({ ...l, kind: 'labour', label: l.description || '' })),
    ]
  }, [q.data])

  function lineDecision(ln: Line & { kind: string }): string {
    const key = `${ln.kind}-${ln.id}`
    const chosen = decisions[key]
    if (chosen === 'approved' || chosen === 'rejected') return chosen
    const current = (ln.approval_status || '').toLowerCase()
    if (current === 'approved' || current === 'rejected') return current
    // Line still pending — default Approve (never send "pending" to API)
    return 'approved'
  }

  const submit = useMutation({
    mutationFn: () =>
      publicPost(`/api/public/quotes/${token}/decide`, {
        decisions: lines.map((ln) => ({
          kind: ln.kind,
          id: ln.id,
          decision: lineDecision(ln),
          media_data_url: media[`${ln.kind}-${ln.id}`],
        })),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['public-quote', token] }),
  })

  function onFile(key: string, file: File | null) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setMedia((m) => ({ ...m, [key]: String(reader.result) }))
    reader.readAsDataURL(file)
  }

  if (q.isLoading) return <p className="muted" style={{ padding: 24 }}>Loading quote…</p>
  if (q.error) return <p className="error-box" style={{ margin: 24 }}>{(q.error as Error).message}</p>
  const data = q.data
  if (!data) return null

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '1.5rem' }}>
      <h1 style={{ fontFamily: 'Georgia, serif' }}>GermanATO</h1>
      <p>
        Quote #{data.invoice_id} for {data.customer_name} ({data.customer_reg_no})
      </p>
      <p>
        Total: <Money value={data.net_total} />
      </p>
      {submit.error ? <p className="error-box">{(submit.error as Error).message}</p> : null}
      {submit.isSuccess ? <p className="muted">Thank you — your decisions were saved.</p> : null}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Line</th>
              <th>Price</th>
              <th>Decision</th>
              <th>Photo / video</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((ln) => {
              const key = `${ln.kind}-${ln.id}`
              const locked =
                ln.approval_status === 'approved' || ln.approval_status === 'rejected'
              return (
                <tr key={key}>
                  <td>
                    {ln.label}
                    {ln.quantity ? ` × ${ln.quantity}` : ''}
                  </td>
                  <td>
                    <Money value={ln.price} />
                  </td>
                  <td>
                    <select
                      className="input"
                      value={lineDecision(ln)}
                      onChange={(e) => setDecisions({ ...decisions, [key]: e.target.value })}
                      disabled={locked}
                    >
                      <option value="approved">Approve</option>
                      <option value="rejected">Reject</option>
                    </select>
                  </td>
                  <td>
                    <input
                      type="file"
                      accept="image/*,video/*"
                      disabled={locked}
                      onChange={(e) => onFile(key, e.target.files?.[0] || null)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn" style={{ marginTop: 16 }} disabled={submit.isPending} onClick={() => submit.mutate()}>
        Submit decisions
      </button>
    </div>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { SignaturePad } from '../components/SignaturePad'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  PageHeader,
  Panel,
} from '../components/ui'

type Customer = { id: number; name: string; phone?: string }
type Car = {
  id: number
  make: string
  model: string
  plate_no?: string
  mileage?: string
  vin?: string
  color?: string
  customer_id?: number | null
  customer_name?: string
  customer_phone?: string
}

type HistoryEvent = {
  kind: string
  at: string | null
  title: string
  summary: string
  href?: string | null
  meta?: Record<string, unknown>
}

type HistoryPayload = {
  car: Car
  events: HistoryEvent[]
  count: number
}

type TemplatePoint = {
  key: string
  label: string
  category: string
  requires_photo?: boolean
}

type InspectItemState = {
  result: 'ok' | 'issue' | 'na'
  notes: string
  photo_data_url: string | null
}

type Visit = {
  id: number
  odometer?: string
  fuel_level?: string
  reported_complaints?: string
  existing_damage?: string
  signature_path?: string
  is_comeback?: boolean
  repair_order_id?: number | null
  check_in_at?: string
  items?: Array<{
    point_key: string
    label: string
    category: string
    result: string
    notes?: string
    photo_path?: string
  }>
}

const KIND_OPTIONS = [
  { id: 'visit', label: 'Visits' },
  { id: 'comeback', label: 'Comebacks' },
  { id: 'ownership', label: 'Ownership' },
  { id: 'quote', label: 'Quotes' },
  { id: 'invoice', label: 'Invoices' },
  { id: 'payment', label: 'Payments' },
  { id: 'repair_order', label: 'Repair orders' },
  { id: 'parts', label: 'Parts' },
]

async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export function CarDetailPage() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const carId = Number(id)
  const qc = useQueryClient()
  const initialTab = (params.get('tab') as 'history' | 'transfer' | 'checkin') || 'history'
  const [tab, setTab] = useState<'history' | 'transfer' | 'checkin'>(initialTab)
  const [kinds, setKinds] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [toCustomerId, setToCustomerId] = useState('')
  const [reason, setReason] = useState('')
  const [transferDate, setTransferDate] = useState(
    () => new Date().toISOString().slice(0, 10),
  )
  const [evidence, setEvidence] = useState<File | null>(null)

  const [odometer, setOdometer] = useState('')
  const [fuel, setFuel] = useState('half')
  const [complaints, setComplaints] = useState('')
  const [damage, setDamage] = useState('')
  const [signature, setSignature] = useState<string | null>(null)
  const [inspect, setInspect] = useState<Record<string, InspectItemState>>({})
  const [printVisitId, setPrintVisitId] = useState<number | null>(
    params.get('visit') ? Number(params.get('visit')) : null,
  )

  const customers = useQuery({
    queryKey: ['customers'],
    queryFn: () => api.get<Customer[]>('/api/customers'),
  })

  const kindsParam = kinds.length ? `&kinds=${kinds.join(',')}` : ''
  const history = useQuery({
    queryKey: ['car-history', carId, kinds.join(',')],
    enabled: Number.isFinite(carId) && carId > 0,
    queryFn: () =>
      api.get<HistoryPayload>(`/api/cars/${carId}/history?${kindsParam}`),
  })

  const template = useQuery({
    queryKey: ['inspection-template'],
    queryFn: () =>
      api.get<{ template: { points: TemplatePoint[] } }>(
        '/api/inspection-templates/default',
      ),
  })

  const visits = useQuery({
    queryKey: ['car-visits', carId],
    enabled: Number.isFinite(carId) && carId > 0,
    queryFn: () =>
      api.get<{ visits: Visit[] }>(`/api/cars/${carId}/visits`),
  })

  const sheet = useQuery({
    queryKey: ['check-in-sheet', printVisitId],
    enabled: !!printVisitId,
    queryFn: () =>
      api.get<{
        title: string
        printed_at: string
        visit: Visit
        car: Car
        customer: { name?: string; phone?: string }
      }>(`/api/visits/${printVisitId}/check-in-sheet`),
  })

  const points = template.data?.template.points || []

  const transfer = useMutation({
    mutationFn: async () => {
      if (!evidence) throw new Error('Evidence file is required')
      const form = new FormData()
      form.append('to_customer_id', toCustomerId)
      form.append('reason', reason)
      form.append('transfer_date', transferDate)
      form.append('evidence', evidence)
      return api.post(`/api/cars/${carId}/transfer`, form, { reason })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['car-history', carId] })
      qc.invalidateQueries({ queryKey: ['cars'] })
      setReason('')
      setEvidence(null)
      setTab('history')
    },
  })

  const checkIn = useMutation({
    mutationFn: () =>
      api.post<{ visit: Visit }>(`/api/cars/${carId}/visits`, {
        odometer,
        fuel_level: fuel,
        reported_complaints: complaints,
        existing_damage: damage,
        signature_data_url: signature,
        items: points.map((p) => ({
          key: p.key,
          result: inspect[p.key]?.result || 'ok',
          notes: inspect[p.key]?.notes || '',
          photo_data_url: inspect[p.key]?.photo_data_url || null,
        })),
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['car-history', carId] })
      qc.invalidateQueries({ queryKey: ['car-visits', carId] })
      setSignature(null)
      setComplaints('')
      setDamage('')
      setInspect({})
      setPrintVisitId(data.visit.id)
      setTab('checkin')
    },
  })

  const filteredEvents = useMemo(() => {
    const events = history.data?.events || []
    const q = search.trim().toLowerCase()
    if (!q) return events
    return events.filter(
      (e) =>
        e.title.toLowerCase().includes(q) ||
        e.summary.toLowerCase().includes(q) ||
        e.kind.toLowerCase().includes(q),
    )
  }, [history.data, search])

  const car = history.data?.car

  function switchTab(next: 'history' | 'transfer' | 'checkin') {
    setTab(next)
    const nextParams = new URLSearchParams(params)
    nextParams.set('tab', next)
    setParams(nextParams, { replace: true })
  }

  function toggleKind(id: string) {
    setKinds((prev) =>
      prev.includes(id) ? prev.filter((k) => k !== id) : [...prev, id],
    )
  }

  function onTransfer(e: FormEvent) {
    e.preventDefault()
    transfer.mutate()
  }

  function onCheckIn(e: FormEvent) {
    e.preventDefault()
    checkIn.mutate()
  }

  function setItem(key: string, patch: Partial<InspectItemState>) {
    setInspect((prev) => ({
      ...prev,
      [key]: {
        result: prev[key]?.result || 'ok',
        notes: prev[key]?.notes || '',
        photo_data_url: prev[key]?.photo_data_url || null,
        ...patch,
      },
    }))
  }

  if (!Number.isFinite(carId) || carId <= 0) {
    return <ErrorBox error="Invalid car id" />
  }

  return (
    <div>
      <PageHeader
        title={
          car
            ? `${car.make} ${car.model} · ${car.plate_no || 'No plate'}`
            : `Car #${carId}`
        }
        actions={
          <Link className="btn btn-secondary" to="/cars">
            Back to cars
          </Link>
        }
      />

      {history.isLoading ? <Loading /> : null}
      {history.error ? <ErrorBox error={history.error} /> : null}

      {car ? (
        <Panel title="Vehicle">
          <div className="stat-grid">
            <div className="stat">
              <div className="label">Owner</div>
              <div className="value" style={{ fontSize: '1rem' }}>
                {car.customer_name || 'Unassigned'}
              </div>
            </div>
            <div className="stat">
              <div className="label">VIN</div>
              <div className="value" style={{ fontSize: '1rem' }}>
                {car.vin || '—'}
              </div>
            </div>
            <div className="stat">
              <div className="label">Odometer</div>
              <div className="value" style={{ fontSize: '1rem' }}>
                {car.mileage || '—'}
              </div>
            </div>
            <div className="stat">
              <div className="label">Phone</div>
              <div className="value" style={{ fontSize: '1rem' }}>
                {car.customer_phone || '—'}
              </div>
            </div>
          </div>
        </Panel>
      ) : null}

      <div className="tabs">
        {(['history', 'checkin', 'transfer'] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`tab${tab === t ? ' is-active' : ''}`}
            onClick={() => switchTab(t)}
          >
            {t === 'history'
              ? 'History'
              : t === 'checkin'
                ? 'Check-in'
                : 'Transfer ownership'}
          </button>
        ))}
      </div>

      {tab === 'history' ? (
        <Panel
          title="Car history"
          actions={
            <input
              className="input"
              placeholder="Filter timeline"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 200 }}
            />
          }
        >
          <div className="row-actions" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
            {KIND_OPTIONS.map((k) => (
              <button
                key={k.id}
                type="button"
                className={`btn btn-sm${kinds.includes(k.id) ? '' : ' btn-secondary'}`}
                onClick={() => toggleKind(k.id)}
              >
                {k.label}
              </button>
            ))}
            {kinds.length ? (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setKinds([])}
              >
                Clear filters
              </button>
            ) : null}
          </div>

          {!history.isLoading && !filteredEvents.length ? (
            <Empty>No history events</Empty>
          ) : null}

          <ul className="timeline">
            {filteredEvents.map((ev, idx) => (
              <li key={`${ev.kind}-${ev.at}-${idx}`} className="timeline-item">
                <div className="timeline-kind">{ev.kind.replaceAll('_', ' ')}</div>
                <div className="timeline-body">
                  <div className="timeline-title">
                    {ev.href ? <Link to={ev.href}>{ev.title}</Link> : ev.title}
                  </div>
                  <div className="muted">{ev.summary}</div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {ev.at || '—'}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

      {tab === 'transfer' ? (
        <Panel title="Transfer ownership">
          <p className="muted">
            History stays on this car. Old invoices and quotes remain linked to the
            original customer. Evidence upload is required.
          </p>
          {transfer.error ? <ErrorBox error={transfer.error} /> : null}
          <FormGrid onSubmit={onTransfer}>
            <Field label="New owner">
              <select
                required
                value={toCustomerId}
                onChange={(e) => setToCustomerId(e.target.value)}
              >
                <option value="">Select customer</option>
                {(customers.data || [])
                  .filter((c) => c.id !== car?.customer_id)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.phone ? `(${c.phone})` : ''}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Transfer date">
              <input
                type="date"
                required
                value={transferDate}
                onChange={(e) => setTransferDate(e.target.value)}
              />
            </Field>
            <Field label="Reason">
              <input
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Sale, gift, fleet reassignment…"
              />
            </Field>
            <Field label="Evidence (required)">
              <input
                type="file"
                required
                accept="image/*,.pdf"
                onChange={(e) => setEvidence(e.target.files?.[0] || null)}
              />
            </Field>
            <button
              className="btn"
              type="submit"
              disabled={transfer.isPending || !evidence || !toCustomerId || !reason}
            >
              {transfer.isPending ? 'Transferring…' : 'Transfer car'}
            </button>
          </FormGrid>
        </Panel>
      ) : null}

      {tab === 'checkin' ? (
        <>
          <Panel title="New check-in / digital inspection">
            <p className="muted">
              Capture odometer, fuel, complaints, multi-point inspection (with phone
              camera photos), and customer signature before opening a job card.
            </p>
            {checkIn.error ? <ErrorBox error={checkIn.error} /> : null}
            <form onSubmit={onCheckIn} className="stack">
              <FormGrid>
                <Field label="Odometer">
                  <input
                    required
                    value={odometer || car?.mileage || ''}
                    onChange={(e) => setOdometer(e.target.value)}
                  />
                </Field>
                <Field label="Fuel level">
                  <select value={fuel} onChange={(e) => setFuel(e.target.value)}>
                    <option value="empty">Empty</option>
                    <option value="quarter">1/4</option>
                    <option value="half">1/2</option>
                    <option value="three_quarter">3/4</option>
                    <option value="full">Full</option>
                  </select>
                </Field>
                <Field label="Reported complaints">
                  <textarea
                    rows={2}
                    value={complaints}
                    onChange={(e) => setComplaints(e.target.value)}
                  />
                </Field>
                <Field label="Existing damage notes">
                  <textarea
                    rows={2}
                    value={damage}
                    onChange={(e) => setDamage(e.target.value)}
                  />
                </Field>
              </FormGrid>

              <h3 style={{ marginTop: 16 }}>Inspection checklist</h3>
              {template.isLoading ? <Loading /> : null}
              {points.map((p) => (
                <div
                  key={p.key}
                  className="panel"
                  style={{ padding: 12, marginBottom: 8 }}
                >
                  <div style={{ fontWeight: 600 }}>
                    {p.label}{' '}
                    <span className="muted" style={{ fontWeight: 400 }}>
                      ({p.category})
                    </span>
                  </div>
                  <div className="row-actions" style={{ marginTop: 8, gap: 8 }}>
                    {(['ok', 'issue', 'na'] as const).map((r) => (
                      <label key={r} style={{ display: 'flex', gap: 4 }}>
                        <input
                          type="radio"
                          name={`result-${p.key}`}
                          checked={(inspect[p.key]?.result || 'ok') === r}
                          onChange={() => setItem(p.key, { result: r })}
                        />
                        {r}
                      </label>
                    ))}
                  </div>
                  <Field label="Notes">
                    <input
                      value={inspect[p.key]?.notes || ''}
                      onChange={(e) => setItem(p.key, { notes: e.target.value })}
                    />
                  </Field>
                  <Field label="Photo (camera or gallery)">
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      onChange={async (e) => {
                        const file = e.target.files?.[0]
                        if (!file) return
                        const url = await fileToDataUrl(file)
                        setItem(p.key, { photo_data_url: url })
                      }}
                    />
                    {inspect[p.key]?.photo_data_url ? (
                      <img
                        src={inspect[p.key]!.photo_data_url!}
                        alt={p.label}
                        style={{ maxWidth: 160, marginTop: 8, borderRadius: 4 }}
                      />
                    ) : null}
                  </Field>
                </div>
              ))}

              <h3>Customer signature (required)</h3>
              <SignaturePad value={signature} onChange={setSignature} />

              <button
                className="btn"
                type="submit"
                disabled={checkIn.isPending || !signature || !points.length}
                style={{ marginTop: 12 }}
              >
                {checkIn.isPending ? 'Saving…' : 'Complete check-in'}
              </button>
            </form>
          </Panel>

          <Panel title="Past check-ins">
            {(visits.data?.visits || []).length === 0 ? <Empty /> : null}
            <ul className="timeline">
              {(visits.data?.visits || []).map((v) => (
                <li key={v.id} className="timeline-item">
                  <div className="timeline-kind">
                    {v.is_comeback ? 'comeback' : 'visit'}
                  </div>
                  <div className="timeline-body">
                    <div className="timeline-title">
                      Check-in #{v.id} · {v.check_in_at || '—'}
                    </div>
                    <div className="muted">
                      odometer {v.odometer || '—'} · fuel {v.fuel_level || '—'}
                      {v.repair_order_id ? ` · RO #${v.repair_order_id}` : ''}
                    </div>
                    <div className="row-actions" style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setPrintVisitId(v.id)}
                      >
                        Printable sheet
                      </button>
                      {!v.repair_order_id ? (
                        <Link
                          className="btn btn-sm"
                          to={`/job-cards/new?car_id=${carId}&visit_id=${v.id}`}
                        >
                          Create job card
                        </Link>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>

          {printVisitId && sheet.data ? (
            <Panel
              title="Check-in sheet"
              actions={
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => window.print()}
                >
                  Print
                </button>
              }
            >
              <div className="checkin-sheet">
                <h2>{sheet.data.title}</h2>
                <p className="muted">Printed {sheet.data.printed_at}</p>
                <p>
                  <strong>
                    {sheet.data.car.make} {sheet.data.car.model}
                  </strong>{' '}
                  · {sheet.data.car.plate_no || '—'} · VIN {sheet.data.car.vin || '—'}
                </p>
                <p>
                  Customer: {sheet.data.customer.name || '—'} (
                  {sheet.data.customer.phone || '—'})
                </p>
                <p>
                  Odometer: {sheet.data.visit.odometer || '—'} · Fuel:{' '}
                  {sheet.data.visit.fuel_level || '—'}
                </p>
                <p>Complaints: {sheet.data.visit.reported_complaints || '—'}</p>
                <p>Existing damage: {sheet.data.visit.existing_damage || '—'}</p>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Point</th>
                      <th>Category</th>
                      <th>Result</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sheet.data.visit.items || []).map((i) => (
                      <tr key={i.point_key}>
                        <td>{i.label}</td>
                        <td>{i.category}</td>
                        <td>{i.result}</td>
                        <td>{i.notes || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {sheet.data.visit.signature_path ? (
                  <div style={{ marginTop: 16 }}>
                    <div className="muted">Customer signature</div>
                    <img
                      src={`/${(sheet.data.visit.signature_path || '').replace(/^\/?uploads\//, 'uploads/')}`}
                      alt="Signature"
                      style={{ maxWidth: 280, border: '1px solid #ddd' }}
                    />
                  </div>
                ) : null}
              </div>
            </Panel>
          ) : null}
        </>
      ) : null}
    </div>
  )
}

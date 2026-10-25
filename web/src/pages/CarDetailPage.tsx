import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
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

const KIND_OPTIONS = [
  { id: 'ownership', label: 'Ownership' },
  { id: 'quote', label: 'Quotes' },
  { id: 'invoice', label: 'Invoices' },
  { id: 'payment', label: 'Payments' },
  { id: 'repair_order', label: 'Repair orders' },
  { id: 'parts', label: 'Parts' },
]

export function CarDetailPage() {
  const { id } = useParams()
  const carId = Number(id)
  const qc = useQueryClient()
  const [tab, setTab] = useState<'history' | 'transfer'>('history')
  const [kinds, setKinds] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [toCustomerId, setToCustomerId] = useState('')
  const [reason, setReason] = useState('')
  const [transferDate, setTransferDate] = useState(
    () => new Date().toISOString().slice(0, 10),
  )
  const [evidence, setEvidence] = useState<File | null>(null)

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

  function toggleKind(id: string) {
    setKinds((prev) =>
      prev.includes(id) ? prev.filter((k) => k !== id) : [...prev, id],
    )
  }

  function onTransfer(e: FormEvent) {
    e.preventDefault()
    transfer.mutate()
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
        <button
          type="button"
          className={`tab${tab === 'history' ? ' is-active' : ''}`}
          onClick={() => setTab('history')}
        >
          History
        </button>
        <button
          type="button"
          className={`tab${tab === 'transfer' ? ' is-active' : ''}`}
          onClick={() => setTab('transfer')}
        >
          Transfer ownership
        </button>
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
      ) : (
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
      )}
    </div>
  )
}

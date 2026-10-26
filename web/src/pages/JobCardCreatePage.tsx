import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Field, PageHeader, Panel } from '../components/ui'

type LabourCode = { id: number; code: string; description: string; standard_hours: number; rate: number }
type InvItem = { id: number; name: string; part_number?: string; price?: number; quantity?: number }

type Line = {
  line_type: 'labour' | 'part'
  labour_code_id?: number
  inventory_id?: number
  description: string
  quantity: number
  unit_price: number
  std_hours?: number
  pay_type: string
  assigned_technician?: string
  line_status: string
}

export function JobCardCreatePage() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [customer_name, setName] = useState('')
  const [customer_phone, setPhone] = useState('')
  const [customer_reg_no, setReg] = useState('')
  const [customer_made, setMade] = useState('')
  const [visit_id, setVisitId] = useState(params.get('visit_id') || '')
  const [car_id, setCarId] = useState(params.get('car_id') || '')
  const [customer_id, setCustomerId] = useState(params.get('customer_id') || '')
  const [lines, setLines] = useState<Line[]>([])
  const [invQ, setInvQ] = useState('')

  const codes = useQuery({
    queryKey: ['labour-codes'],
    queryFn: () => api.get<LabourCode[]>('/api/labour-codes'),
  })

  const inventory = useQuery({
    queryKey: ['inv-picker', invQ],
    queryFn: async () => {
      const data = await api.get<{ items?: InvItem[] } | InvItem[]>(
        `/api/inventory?q=${encodeURIComponent(invQ)}&limit=20`,
      )
      if (Array.isArray(data)) return data
      return data.items || []
    },
  })

  const create = useMutation({
    mutationFn: () =>
      api.post<{ id: number }>('/api/job-cards', {
        customer_name,
        customer_phone,
        customer_reg_no,
        customer_made,
        visit_id: visit_id ? Number(visit_id) : null,
        car_id: car_id ? Number(car_id) : null,
        customer_id: customer_id ? Number(customer_id) : null,
        lines,
      }),
    onSuccess: (row) => nav(`/job-cards/${row.id}`),
  })

  const invOptions = useMemo(() => inventory.data || [], [inventory.data])

  function addLabour(code?: LabourCode) {
    setLines((prev) => [
      ...prev,
      {
        line_type: 'labour',
        labour_code_id: code?.id,
        description: code?.description || '',
        quantity: 1,
        unit_price: code?.rate || 0,
        std_hours: code?.standard_hours,
        pay_type: 'customer',
        line_status: 'Pending',
      },
    ])
  }

  function addPart(item: InvItem) {
    setLines((prev) => [
      ...prev,
      {
        line_type: 'part',
        inventory_id: item.id,
        description: item.name,
        quantity: 1,
        unit_price: Number(item.price || 0),
        pay_type: 'customer',
        line_status: 'Pending',
        part_number: item.part_number,
      } as Line,
    ])
  }

  return (
    <div>
      <PageHeader title="New job card" />
      <Panel title="Vehicle / customer">
        {create.error ? <ErrorBox error={create.error} /> : null}
        <div className="form-grid">
          <Field label="Customer">
            <input className="input" value={customer_name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Phone">
            <input className="input" value={customer_phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>
          <Field label="Reg no">
            <input className="input" value={customer_reg_no} onChange={(e) => setReg(e.target.value)} />
          </Field>
          <Field label="Make / model">
            <input className="input" value={customer_made} onChange={(e) => setMade(e.target.value)} />
          </Field>
          <Field label="Visit ID">
            <input className="input" value={visit_id} onChange={(e) => setVisitId(e.target.value)} />
          </Field>
          <Field label="Car ID">
            <input className="input" value={car_id} onChange={(e) => setCarId(e.target.value)} />
          </Field>
          <Field label="Customer ID">
            <input className="input" value={customer_id} onChange={(e) => setCustomerId(e.target.value)} />
          </Field>
        </div>
      </Panel>
      <Panel title="Labour catalogue">
        <div className="form-grid">
          {(codes.data || []).slice(0, 12).map((c) => (
            <button key={c.id} type="button" className="btn btn-ghost" onClick={() => addLabour(c)}>
              {c.code} — {c.description}
            </button>
          ))}
          <button type="button" className="btn btn-ghost" onClick={() => addLabour()}>
            Custom labour
          </button>
        </div>
      </Panel>
      <Panel title="Parts from inventory">
        <Field label="Search parts">
          <input className="input" value={invQ} onChange={(e) => setInvQ(e.target.value)} />
        </Field>
        <div className="form-grid">
          {invOptions.map((i) => (
            <button key={i.id} type="button" className="btn btn-ghost" onClick={() => addPart(i)}>
              {i.part_number} {i.name} (stock {i.quantity})
            </button>
          ))}
        </div>
      </Panel>
      <Panel title="Lines">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Type</th>
                <th>Description</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Pay</th>
                <th>Tech</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((ln, idx) => (
                <tr key={idx}>
                  <td>{ln.line_type}</td>
                  <td>
                    <input
                      className="input"
                      value={ln.description}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, description: e.target.value }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      style={{ width: 64 }}
                      value={ln.quantity}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, quantity: Number(e.target.value) || 0 }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      style={{ width: 88 }}
                      value={ln.unit_price}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, unit_price: Number(e.target.value) || 0 }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <select
                      className="input"
                      value={ln.pay_type}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, pay_type: e.target.value }
                        setLines(next)
                      }}
                    >
                      <option value="customer">customer</option>
                      <option value="warranty">warranty</option>
                      <option value="internal">internal</option>
                    </select>
                  </td>
                  <td>
                    <input
                      className="input"
                      value={ln.assigned_technician || ''}
                      onChange={(e) => {
                        const next = [...lines]
                        next[idx] = { ...ln, assigned_technician: e.target.value }
                        setLines(next)
                      }}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => setLines(lines.filter((_, i) => i !== idx))}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" className="btn" disabled={create.isPending || !customer_name} onClick={() => create.mutate()}>
          Save job card
        </button>
      </Panel>
    </div>
  )
}

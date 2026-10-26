import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  Money,
  PageHeader,
  Panel,
} from '../components/ui'

type CashRow = {
  id: number
  date: string
  amount: number
  description?: string
  payment_method?: string
  notes?: string
}

export function CashReceivedPage() {
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const today = new Date().toISOString().slice(0, 10)
  const [from, setFrom] = useState(sp.get('start_date') || today)
  const [to, setTo] = useState(sp.get('end_date') || today)
  const [form, setForm] = useState({
    date: today,
    amount: 0,
    description: '',
    payment_method: 'cash',
    notes: '',
  })
  const [editingId, setEditingId] = useState<number | null>(null)

  const list = useQuery({
    queryKey: ['cash-received', from, to],
    queryFn: async () => {
      const params = new URLSearchParams({ start_date: from, end_date: to })
      const data = await api.get<CashRow[] | { records: CashRow[] }>(
        `/api/cash-received?${params}`,
      )
      return Array.isArray(data) ? data : data.records || []
    },
  })

  const save = useMutation({
    mutationFn: async () => {
      const body = { ...form, amount: Number(form.amount) }
      if (editingId) return api.put(`/api/cash-received/${editingId}`, body)
      return api.post('/api/cash-received', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cash-received'] })
      setEditingId(null)
      setForm({
        date: today,
        amount: 0,
        description: '',
        payment_method: 'cash',
        notes: '',
      })
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/cash-received/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cash-received'] }),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div>
      <PageHeader title="Cash received" />
      <Panel title={editingId ? 'Edit receipt' : 'Record cash'}>
        {save.error ? <ErrorBox error={save.error} /> : null}
        <FormGrid onSubmit={onSubmit}>
          <Field label="Date">
            <input
              type="date"
              required
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
          </Field>
          <Field label="Amount">
            <input
              type="number"
              step="0.01"
              required
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
            />
          </Field>
          <Field label="Description">
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <Field label="Method">
            <select
              value={form.payment_method}
              onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
            >
              <option value="cash">Cash</option>
              <option value="bank">Bank</option>
              <option value="card">Card</option>
            </select>
          </Field>
          <Field label="Notes">
            <input
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Field>
          <button className="btn" type="submit" disabled={save.isPending}>
            {editingId ? 'Update' : 'Add'}
          </button>
        </FormGrid>
      </Panel>
      <Panel
        title="Receipts"
        actions={
          <div className="row-actions">
            <input type="date" className="input" value={from} onChange={(e) => setFrom(e.target.value)} />
            <input type="date" className="input" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        }
      >
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && !(list.data || []).length ? <Empty /> : null}
        {(list.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Method</th>
                  <th>Amount</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((row) => (
                  <tr key={row.id}>
                    <td>{row.date}</td>
                    <td>{row.description}</td>
                    <td>{row.payment_method}</td>
                    <td>
                      <Money value={row.amount} />
                    </td>
                    <td className="row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setEditingId(row.id)
                          setForm({
                            date: row.date,
                            amount: row.amount,
                            description: row.description || '',
                            payment_method: row.payment_method || 'cash',
                            notes: row.notes || '',
                          })
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete?')) remove.mutate(row.id)
                        }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </div>
  )
}

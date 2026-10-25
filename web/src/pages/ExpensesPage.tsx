import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
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

type Expense = {
  id: number
  date: string
  category: string
  description: string
  amount: number
  notes?: string
}

const DAILY_CATEGORIES = [
  'Fuel',
  'Utilities',
  'Supplies',
  'Maintenance',
  'Transport',
  'Food',
  'Other',
]

const MAJOR_CATEGORIES = [
  'Equipment',
  'Rent',
  'Payroll',
  'Capital',
  'Insurance',
  'Other major',
]

export function ExpensesPage({
  mode,
}: {
  mode: 'daily' | 'major'
}) {
  const qc = useQueryClient()
  const title = mode === 'daily' ? 'Daily expenses' : 'Major expenses'
  const categories = mode === 'daily' ? DAILY_CATEGORIES : MAJOR_CATEGORIES
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    date: today,
    category: categories[0],
    description: '',
    amount: 0,
    notes: '',
  })
  const [editingId, setEditingId] = useState<number | null>(null)
  const [from, setFrom] = useState(today)
  const [to, setTo] = useState(today)

  const list = useQuery({
    queryKey: ['expenses', mode, from, to],
    queryFn: async () => {
      const params = new URLSearchParams({
        start_date: from,
        end_date: to,
      })
      if (mode === 'daily') params.set('scope', 'till')
      if (mode === 'major') params.set('scope', 'major')
      const data = await api.get<Expense[] | { expenses: Expense[] }>(
        `/api/expenses?${params}`,
      )
      return Array.isArray(data) ? data : data.expenses || []
    },
  })

  const save = useMutation({
    mutationFn: async () => {
      const body = { ...form, amount: Number(form.amount) }
      if (editingId) return api.put(`/api/expenses/${editingId}`, body)
      return api.post('/api/expenses', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['expenses'] })
      setForm({
        date: today,
        category: categories[0],
        description: '',
        amount: 0,
        notes: '',
      })
      setEditingId(null)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/expenses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['expenses'] }),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  const total = (list.data || []).reduce((s, e) => s + Number(e.amount || 0), 0)

  return (
    <div>
      <PageHeader title={title} />
      <div className="stat-grid">
        <div className="stat">
          <div className="label">Range total</div>
          <div className="value">
            <Money value={total} />
          </div>
        </div>
      </div>
      <Panel title={editingId ? 'Edit expense' : 'Add expense'}>
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
          <Field label="Category">
            <select
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Description">
            <input
              required
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
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
        title="Expenses"
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
                  <th>Category</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((exp) => (
                  <tr key={exp.id}>
                    <td>{exp.date}</td>
                    <td>{exp.category}</td>
                    <td>{exp.description}</td>
                    <td>
                      <Money value={exp.amount} />
                    </td>
                    <td className="row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setEditingId(exp.id)
                          setForm({
                            date: exp.date,
                            category: exp.category,
                            description: exp.description,
                            amount: exp.amount,
                            notes: exp.notes || '',
                          })
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete expense?')) remove.mutate(exp.id)
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

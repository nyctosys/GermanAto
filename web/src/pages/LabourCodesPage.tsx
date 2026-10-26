import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { ErrorBox, Field, Loading, PageHeader, Panel } from '../components/ui'

type LabourCode = {
  id: number
  code: string
  description: string
  standard_hours: number
  rate: number
  category: string
}

export function LabourCodesPage() {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    code: '',
    description: '',
    standard_hours: '1',
    rate: '0',
    category: 'general',
  })

  const list = useQuery({
    queryKey: ['labour-codes'],
    queryFn: () => api.get<LabourCode[]>('/api/labour-codes'),
  })

  const create = useMutation({
    mutationFn: () =>
      api.post('/api/labour-codes', {
        code: form.code,
        description: form.description,
        standard_hours: Number(form.standard_hours),
        rate: Number(form.rate),
        category: form.category,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['labour-codes'] })
      setForm({ code: '', description: '', standard_hours: '1', rate: '0', category: 'general' })
    },
  })

  return (
    <div>
      <PageHeader title="Labour codes" />
      <Panel title="Catalogue">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Code</th>
                <th>Description</th>
                <th>Hours</th>
                <th>Rate</th>
                <th>Category</th>
              </tr>
            </thead>
            <tbody>
              {(list.data || []).map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td>
                  <td>{r.description}</td>
                  <td>{r.standard_hours}</td>
                  <td>{r.rate}</td>
                  <td>{r.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Add labour code">
        {create.error ? <ErrorBox error={create.error} /> : null}
        <div className="form-grid">
          <Field label="Code">
            <input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
          <Field label="Description">
            <input
              className="input"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <Field label="Std hours">
            <input
              className="input"
              value={form.standard_hours}
              onChange={(e) => setForm({ ...form, standard_hours: e.target.value })}
            />
          </Field>
          <Field label="Rate">
            <input className="input" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} />
          </Field>
          <Field label="Category">
            <input
              className="input"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
          </Field>
        </div>
        <button type="button" className="btn" disabled={create.isPending} onClick={() => create.mutate()}>
          Save
        </button>
      </Panel>
    </div>
  )
}

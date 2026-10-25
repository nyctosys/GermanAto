import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
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

type Named = { id: number; name: string; is_active?: boolean; description?: string }

type WorkshopSettings = {
  discount_approval_pct: number
  mandatory_receipt_amount: number
  comeback_window_days: number
  payment_gate_enabled: boolean
  expense_heads: string[]
}

const emptyWorkshop: WorkshopSettings = {
  discount_approval_pct: 10,
  mandatory_receipt_amount: 500,
  comeback_window_days: 14,
  payment_gate_enabled: true,
  expense_heads: [],
}

export function SettingsPage() {
  const qc = useQueryClient()
  const [deptName, setDeptName] = useState('')
  const [catName, setCatName] = useState('')
  /** Local draft; null means “show server values”. */
  const [workshopDraft, setWorkshopDraft] = useState<WorkshopSettings | null>(null)
  const [headsDraft, setHeadsDraft] = useState<string | null>(null)

  const departments = useQuery({
    queryKey: ['settings-departments'],
    queryFn: async () => {
      const data = await api.get<Named[] | { departments: Named[] }>(
        '/api/settings/departments?include_inactive=true',
      )
      return Array.isArray(data) ? data : data.departments || []
    },
  })

  const categories = useQuery({
    queryKey: ['settings-categories'],
    queryFn: async () => {
      const data = await api.get<Named[] | { categories: Named[] }>(
        '/api/settings/categories?include_inactive=true',
      )
      return Array.isArray(data) ? data : data.categories || []
    },
  })

  const workshopQ = useQuery({
    queryKey: ['settings-workshop'],
    queryFn: () =>
      api.get<{ settings: WorkshopSettings }>('/api/settings/workshop'),
  })

  const workshop = workshopDraft ?? workshopQ.data?.settings ?? emptyWorkshop
  const headsText =
    headsDraft ?? (workshopQ.data?.settings.expense_heads || []).join('\n')

  const addDept = useMutation({
    mutationFn: () => api.post('/api/settings/departments', { name: deptName }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings-departments'] })
      setDeptName('')
    },
  })

  const addCat = useMutation({
    mutationFn: () => api.post('/api/settings/categories', { name: catName }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings-categories'] })
      setCatName('')
    },
  })

  const delDept = useMutation({
    mutationFn: (id: number) => api.delete(`/api/settings/departments/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings-departments'] }),
  })

  const delCat = useMutation({
    mutationFn: (id: number) => api.delete(`/api/settings/categories/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings-categories'] }),
  })

  const saveWorkshop = useMutation({
    mutationFn: () =>
      api.put('/api/settings/workshop', {
        settings: {
          ...workshop,
          expense_heads: headsText
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean),
        },
      }),
    onSuccess: () => {
      setWorkshopDraft(null)
      setHeadsDraft(null)
      qc.invalidateQueries({ queryKey: ['settings-workshop'] })
    },
  })

  return (
    <div>
      <PageHeader title="Settings" />
      <Panel title="Workshop thresholds">
        {saveWorkshop.error ? <ErrorBox error={saveWorkshop.error} /> : null}
        {workshopQ.isLoading ? <Loading /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            saveWorkshop.mutate()
          }}
        >
          <Field label="Discount approval % (above → manager + reason)">
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={workshop.discount_approval_pct}
              onChange={(e) =>
                setWorkshopDraft({
                  ...workshop,
                  discount_approval_pct: Number(e.target.value),
                })
              }
            />
          </Field>
          <Field label="Mandatory receipt amount (Rs)">
            <input
              type="number"
              min={0}
              step={1}
              value={workshop.mandatory_receipt_amount}
              onChange={(e) =>
                setWorkshopDraft({
                  ...workshop,
                  mandatory_receipt_amount: Number(e.target.value),
                })
              }
            />
          </Field>
          <Field label="Comeback window (days)">
            <input
              type="number"
              min={0}
              step={1}
              value={workshop.comeback_window_days}
              onChange={(e) =>
                setWorkshopDraft({
                  ...workshop,
                  comeback_window_days: Number(e.target.value),
                })
              }
            />
          </Field>
          <Field label="Payment gate">
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={workshop.payment_gate_enabled}
                onChange={(e) =>
                  setWorkshopDraft({
                    ...workshop,
                    payment_gate_enabled: e.target.checked,
                  })
                }
              />
              Enabled
            </label>
          </Field>
          <Field label="Expense heads (one per line)">
            <textarea
              rows={5}
              value={headsText}
              onChange={(e) => setHeadsDraft(e.target.value)}
            />
          </Field>
          <button className="btn" type="submit" disabled={saveWorkshop.isPending}>
            Save workshop settings
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Departments">
        {addDept.error ? <ErrorBox error={addDept.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addDept.mutate()
          }}
        >
          <Field label="Name">
            <input
              required
              value={deptName}
              onChange={(e) => setDeptName(e.target.value)}
            />
          </Field>
          <button className="btn" type="submit">
            Add department
          </button>
        </FormGrid>
        {departments.isLoading ? <Loading /> : null}
        {!departments.isLoading && !(departments.data || []).length ? <Empty /> : null}
        {(departments.data || []).length > 0 ? (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Active</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(departments.data || []).map((d) => (
                  <tr key={d.id}>
                    <td>{d.name}</td>
                    <td>{d.is_active === false ? 'no' : 'yes'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete department?')) delDept.mutate(d.id)
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

      <Panel title="Inventory categories">
        {addCat.error ? <ErrorBox error={addCat.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addCat.mutate()
          }}
        >
          <Field label="Name">
            <input required value={catName} onChange={(e) => setCatName(e.target.value)} />
          </Field>
          <button className="btn" type="submit">
            Add category
          </button>
        </FormGrid>
        {categories.isLoading ? <Loading /> : null}
        {!categories.isLoading && !(categories.data || []).length ? <Empty /> : null}
        {(categories.data || []).length > 0 ? (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Active</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(categories.data || []).map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>{c.is_active === false ? 'no' : 'yes'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete category?')) delCat.mutate(c.id)
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

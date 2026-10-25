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

export function SettingsPage() {
  const qc = useQueryClient()
  const [deptName, setDeptName] = useState('')
  const [catName, setCatName] = useState('')

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

  return (
    <div>
      <PageHeader title="Settings" />
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

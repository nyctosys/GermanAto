import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useEffect, useState, type FormEvent } from 'react'
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

type Vendor = {
  id: number
  name: string
  company_name?: string
  contact_person?: string
  phone?: string
  email?: string
  address?: string
  cnic?: string
}

const empty = {
  name: '',
  company_name: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  cnic: '',
}

export function VendorsPage() {
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const [form, setForm] = useState(empty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    if (params.get('new') === '1') setShowForm(true)
  }, [params])

  const list = useQuery({
    queryKey: ['vendors'],
    queryFn: () => api.get<Vendor[] | { vendors: Vendor[] }>('/api/vendors'),
  })
  const vendors = Array.isArray(list.data) ? list.data : list.data?.vendors || []

  const save = useMutation({
    mutationFn: async () => {
      if (editingId) return api.put(`/api/vendors/${editingId}`, form)
      return api.post('/api/vendors', form)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendors'] })
      setForm(empty)
      setEditingId(null)
      setShowForm(false)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/vendors/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div>
      <PageHeader
        title="Vendors"
        actions={
          <button type="button" className="btn" onClick={() => setShowForm(true)}>
            New vendor
          </button>
        }
      />
      {showForm ? (
        <Panel title={editingId ? 'Edit vendor' : 'Add vendor'}>
          {save.error ? <ErrorBox error={save.error} /> : null}
          <FormGrid onSubmit={onSubmit}>
            {(
              [
                ['name', 'Name'],
                ['company_name', 'Company'],
                ['contact_person', 'Contact'],
                ['phone', 'Phone'],
                ['email', 'Email'],
                ['address', 'Address'],
                ['cnic', 'CNIC'],
              ] as const
            ).map(([key, label]) => (
              <Field key={key} label={label}>
                <input
                  required={key === 'name'}
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              </Field>
            ))}
            <button className="btn" type="submit" disabled={save.isPending}>
              Save
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setShowForm(false)
                setEditingId(null)
                setForm(empty)
              }}
            >
              Cancel
            </button>
          </FormGrid>
        </Panel>
      ) : null}
      <Panel title="Vendor list">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && vendors.length === 0 ? <Empty /> : null}
        {vendors.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Company</th>
                  <th>Phone</th>
                  <th>Contact</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <Link to={`/vendors/${v.id}`}>{v.name}</Link>
                    </td>
                    <td>{v.company_name || '—'}</td>
                    <td>{v.phone || '—'}</td>
                    <td>{v.contact_person || '—'}</td>
                    <td className="row-actions">
                      <Link className="btn btn-secondary btn-sm" to={`/vendors/${v.id}`}>
                        Open
                      </Link>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setEditingId(v.id)
                          setForm({
                            name: v.name || '',
                            company_name: v.company_name || '',
                            contact_person: v.contact_person || '',
                            phone: v.phone || '',
                            email: v.email || '',
                            address: v.address || '',
                            cnic: v.cnic || '',
                          })
                          setShowForm(true)
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete vendor?')) remove.mutate(v.id)
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

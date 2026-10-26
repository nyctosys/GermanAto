import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
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
  payment_terms_days?: number
  bank_details?: string
  notes?: string
}

const empty = {
  name: '',
  company_name: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  cnic: '',
  payment_terms_days: '30',
  bank_details: '',
  notes: '',
}

export function VendorsPage() {
  const qc = useQueryClient()
  const { confirm } = useConfirm()
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
      const payload = {
        ...form,
        payment_terms_days: Number(form.payment_terms_days || 30),
      }
      if (editingId) return api.put(`/api/vendors/${editingId}`, payload)
      return api.post('/api/vendors', payload)
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
                ['payment_terms_days', 'Payment terms (days)'],
                ['bank_details', 'Bank details'],
                ['notes', 'Notes'],
              ] as const
            ).map(([key, label]) => (
              <Field key={key} label={label}>
                <input
                  required={['name', 'company_name', 'contact_person', 'phone', 'address'].includes(
                    key,
                  )}
                  type={key === 'payment_terms_days' ? 'number' : 'text'}
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
                            payment_terms_days: String(v.payment_terms_days ?? 30),
                            bank_details: v.bank_details || '',
                            notes: v.notes || '',
                          })
                          setShowForm(true)
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={async () => {
                          if (
                            await confirm({
                              message: 'Delete this vendor? This cannot be undone.',
                              danger: true,
                              confirmLabel: 'Delete',
                            })
                          ) {
                            remove.mutate(v.id)
                          }
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

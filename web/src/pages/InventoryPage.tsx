import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
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

type InventoryItem = {
  id: number
  name: string
  category: string
  barcode?: string | null
  manufacturer_part_number?: string | null
  quantity: number
  location?: string | null
  reorder_level?: number
  description?: string | null
}

type InventoryList = {
  items?: InventoryItem[]
  data?: InventoryItem[]
} | InventoryItem[]

function normalizeList(data: InventoryList): InventoryItem[] {
  if (Array.isArray(data)) return data
  return data.items || data.data || []
}

const empty = {
  name: '',
  category: '',
  barcode: '',
  manufacturer_part_number: '',
  quantity: 0,
  location: '',
  reorder_level: 5,
  description: '',
}

export function InventoryPage() {
  const qc = useQueryClient()
  const [form, setForm] = useState(empty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [page, setPage] = useState(1)

  const list = useQuery({
    queryKey: ['inventory', page],
    queryFn: () =>
      api.get<InventoryList>(`/api/inventory?page=${page}&per_page=50`),
  })

  const categories = useQuery({
    queryKey: ['inventory-categories'],
    queryFn: () => api.get<string[] | { categories: string[] }>('/api/inventory/categories'),
  })

  const categoryOptions = Array.isArray(categories.data)
    ? categories.data
    : categories.data?.categories || []

  const items = normalizeList(list.data || [])

  const save = useMutation({
    mutationFn: async () => {
      const body = {
        ...form,
        quantity: Number(form.quantity),
        reorder_level: Number(form.reorder_level),
      }
      if (editingId) return api.put(`/api/inventory/${editingId}`, body)
      return api.post('/api/inventory', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      setForm(empty)
      setEditingId(null)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/inventory/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory'] }),
  })

  const restock = useMutation({
    mutationFn: (id: number) => {
      const qty = Number(prompt('Restock quantity?', '1'))
      if (!qty || qty <= 0) return Promise.reject(new Error('Invalid quantity'))
      return api.post('/api/inventory/restock', { item_id: id, quantity: qty })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory'] }),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div>
      <PageHeader
        title="Inventory"
        actions={
          <Link className="btn btn-secondary" to="/inventory/history">
            History
          </Link>
        }
      />
      <Panel title={editingId ? 'Edit item' : 'Add item'}>
        {save.error ? <ErrorBox error={save.error} /> : null}
        <FormGrid onSubmit={onSubmit}>
          <Field label="Name">
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field label="Category">
            <input
              required
              list="inv-categories"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
            <datalist id="inv-categories">
              {categoryOptions.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </Field>
          <Field label="Barcode">
            <input
              value={form.barcode}
              onChange={(e) => setForm({ ...form, barcode: e.target.value })}
            />
          </Field>
          <Field label="Mfr part #">
            <input
              value={form.manufacturer_part_number}
              onChange={(e) =>
                setForm({ ...form, manufacturer_part_number: e.target.value })
              }
            />
          </Field>
          <Field label="Qty">
            <input
              type="number"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
            />
          </Field>
          <Field label="Reorder level">
            <input
              type="number"
              value={form.reorder_level}
              onChange={(e) =>
                setForm({ ...form, reorder_level: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Location">
            <input
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <button className="btn" type="submit" disabled={save.isPending}>
            {editingId ? 'Update' : 'Create'}
          </button>
        </FormGrid>
      </Panel>
      <Panel title="Stock">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && items.length === 0 ? <Empty /> : null}
        {items.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Category</th>
                  <th>Part #</th>
                  <th>Qty</th>
                  <th>Location</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.name}</td>
                    <td>{item.category}</td>
                    <td>{item.manufacturer_part_number || item.barcode || '—'}</td>
                    <td>{item.quantity}</td>
                    <td>{item.location || '—'}</td>
                    <td className="row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setEditingId(item.id)
                          setForm({
                            name: item.name,
                            category: item.category,
                            barcode: item.barcode || '',
                            manufacturer_part_number:
                              item.manufacturer_part_number || '',
                            quantity: item.quantity,
                            location: item.location || '',
                            reorder_level: item.reorder_level || 5,
                            description: item.description || '',
                          })
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => restock.mutate(item.id)}
                      >
                        Restock
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete item?')) remove.mutate(item.id)
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
        <div className="row-actions" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Prev
          </button>
          <span className="muted">Page {page}</span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </Panel>
    </div>
  )
}

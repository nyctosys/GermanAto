import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
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
  part_number?: string
  barcode?: string | null
  manufacturer_part_number?: string | null
  quantity: number
  on_hand?: number
  reserved?: number
  available?: number
  avg_cost?: number
  location?: string | null
  reorder_level?: number
  min_level?: number | null
  max_level?: number | null
  pending_purchase?: boolean
  description?: string | null
  version?: number
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
  min_level: '',
  max_level: '',
  description: '',
}

function printLabel(payload: {
  print?: { title?: string; subtitle?: string; barcode_value?: string }
}) {
  const title = payload.print?.title || ''
  const subtitle = payload.print?.subtitle || ''
  const code = payload.print?.barcode_value || ''
  const w = window.open('', '_blank', 'width=400,height=300')
  if (!w) return
  w.document.write(`<!doctype html><html><head><title>Label</title>
    <style>
      body{font-family:Georgia,serif;padding:16px;text-align:center}
      h1{font-size:18px;margin:0 0 4px} p{margin:0 0 12px;font-size:12px}
      .code{font-family:ui-monospace,monospace;font-size:22px;letter-spacing:2px;
        border:1px solid #333;padding:10px 16px;display:inline-block}
    </style></head><body>
    <h1>${title.replace(/</g, '')}</h1>
    <p>${subtitle.replace(/</g, '')}</p>
    <div class="code">${code.replace(/</g, '')}</div>
    <script>window.onload=()=>{window.print()}</script>
    </body></html>`)
  w.document.close()
}

export function InventoryPage() {
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const lowStockOnly = sp.get('low_stock') === '1'
  const [form, setForm] = useState(empty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [scan, setScan] = useState('')
  const [scanMsg, setScanMsg] = useState<string | null>(null)
  const scanRef = useRef<HTMLInputElement>(null)

  const list = useQuery({
    queryKey: ['inventory', page],
    queryFn: () =>
      api.get<InventoryList>(`/api/inventory?page=${page}&per_page=50`),
  })

  const categories = useQuery({
    queryKey: ['inventory-categories'],
    queryFn: () => api.get<string[] | { categories: string[] }>('/api/inventory/categories'),
  })

  const reorder = useQuery({
    queryKey: ['inventory-reorder'],
    queryFn: () =>
      api.get<{ suggestions: InventoryItem[]; count: number }>(
        '/api/inventory/reorder-suggestions',
      ),
  })

  const categoryOptions = Array.isArray(categories.data)
    ? categories.data
    : categories.data?.categories || []

  const items = useMemo(() => {
    const all = normalizeList(list.data || [])
    if (!lowStockOnly) return all
    return all.filter((i) => i.quantity <= (i.reorder_level ?? i.min_level ?? 0))
  }, [list.data, lowStockOnly])

  const save = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {
        name: form.name,
        category: form.category,
        barcode: form.barcode,
        manufacturer_part_number: form.manufacturer_part_number,
        location: form.location,
        reorder_level: Number(form.reorder_level),
        description: form.description,
      }
      if (form.min_level !== '') body.min_level = Number(form.min_level)
      if (form.max_level !== '') body.max_level = Number(form.max_level)
      if (editingId) {
        return api.put(`/api/inventory/${editingId}`, body)
      }
      body.quantity = Number(form.quantity)
      return api.post('/api/inventory', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-reorder'] })
      setForm(empty)
      setEditingId(null)
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) =>
      api.delete(`/api/inventory/${id}`, { reason: 'inventory delete' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['inventory'] }),
  })

  async function onScanKey(e: KeyboardEvent<HTMLInputElement>) {
    // USB scanners typically end with Enter
    if (e.key !== 'Enter') return
    e.preventDefault()
    const code = scan.trim()
    if (!code) return
    setScanMsg(null)
    try {
      const data = await api.get<{
        found?: boolean
        item?: InventoryItem
        create_prefill?: Partial<typeof empty> & { barcode?: string }
      }>(`/api/inventory/lookup?code=${encodeURIComponent(code)}`)
      if (data.found && data.item) {
        setScanMsg(`Found: ${data.item.name} (avail ${data.item.available ?? data.item.quantity})`)
        setEditingId(data.item.id)
        setForm({
          name: data.item.name,
          category: data.item.category,
          barcode: data.item.barcode || '',
          manufacturer_part_number: data.item.manufacturer_part_number || '',
          quantity: data.item.quantity,
          location: data.item.location || '',
          reorder_level: data.item.reorder_level || 5,
          min_level: data.item.min_level != null ? String(data.item.min_level) : '',
          max_level: data.item.max_level != null ? String(data.item.max_level) : '',
          description: data.item.description || '',
        })
      } else {
        const prefill = data.create_prefill
        setEditingId(null)
        setForm({
          ...empty,
          barcode: prefill?.barcode || code,
          manufacturer_part_number: prefill?.barcode || code,
        })
        setScanMsg(`Unknown code — create form prefilled with ${code}`)
      }
    } catch (err: unknown) {
      setScanMsg(err instanceof Error ? err.message : 'Lookup failed')
    }
    setScan('')
    scanRef.current?.focus()
  }

  async function onPrintLabel(id: number) {
    const data = await api.get<{
      print?: { title?: string; subtitle?: string; barcode_value?: string }
    }>(`/api/inventory/label/${id}`)
    printLabel(data)
  }

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

      <Panel title="Barcode scan (USB / camera keyboard)">
        <p className="muted" style={{ marginTop: 0 }}>
          Focus the field and scan. Unknown codes open the create form prefilled.
        </p>
        <Field label="Scan code">
          <input
            ref={scanRef}
            autoFocus
            value={scan}
            onChange={(e) => setScan(e.target.value)}
            onKeyDown={onScanKey}
            placeholder="Scan or type barcode, then Enter"
          />
        </Field>
        {scanMsg ? <p className="muted">{scanMsg}</p> : null}
      </Panel>

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
          {!editingId ? (
            <Field label="Opening qty">
              <input
                type="number"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
              />
            </Field>
          ) : null}
          <Field label="Reorder / min">
            <input
              type="number"
              value={form.reorder_level}
              onChange={(e) =>
                setForm({ ...form, reorder_level: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Max level">
            <input
              type="number"
              value={form.max_level}
              onChange={(e) => setForm({ ...form, max_level: e.target.value })}
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
        {editingId ? (
          <p className="muted">
            Stock changes use Adjust (reason + evidence) or PO receive — not this form.
          </p>
        ) : null}
      </Panel>

      {(reorder.data?.suggestions || []).length > 0 ? (
        <Panel title={`Reorder suggestions (${reorder.data?.count})`}>
          <ul>
            {(reorder.data?.suggestions || []).slice(0, 8).map((s) => (
              <li key={s.id}>
                {s.name} — avail {s.available ?? s.quantity} / min{' '}
                {s.min_level ?? s.reorder_level}
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}

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
                  <th>On hand</th>
                  <th>Reserved</th>
                  <th>Avail</th>
                  <th>Avg cost</th>
                  <th>Location</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.name}
                      {item.pending_purchase ? ' (pending)' : ''}
                    </td>
                    <td>{item.category}</td>
                    <td>
                      {item.part_number ||
                        item.manufacturer_part_number ||
                        item.barcode ||
                        '—'}
                    </td>
                    <td>{item.on_hand ?? item.quantity}</td>
                    <td>{item.reserved ?? 0}</td>
                    <td>{item.available ?? item.quantity}</td>
                    <td>{Number(item.avg_cost || 0).toFixed(2)}</td>
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
                            min_level:
                              item.min_level != null ? String(item.min_level) : '',
                            max_level:
                              item.max_level != null ? String(item.max_level) : '',
                            description: item.description || '',
                          })
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => onPrintLabel(item.id)}
                      >
                        Label
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

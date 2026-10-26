import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { api } from '../api/client'
import { useConfirm } from '../components/ConfirmProvider'
import { UnitSelect } from '../components/UnitSelect'
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
  sku?: string
  barcode?: string | null
  manufacturer_part_number?: string | null
  quantity: number
  on_hand?: number
  reserved?: number
  available?: number
  avg_cost?: number
  stock_value?: number
  unit?: string
  pack_size?: number
  packs_on_hand?: number
  loose_pieces?: number
  valuation_method?: string
  location?: string | null
  reorder_level?: number
  reorder_quantity?: number
  min_level?: number | null
  max_level?: number | null
  pending_purchase?: boolean
  preferred_vendor_id?: number | null
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
  sku: '',
  barcode: '',
  manufacturer_part_number: '',
  quantity: 0,
  packs: 0,
  unit: 'pcs',
  pack_size: 1,
  unit_cost: 0,
  location: '',
  reorder_level: 5,
  reorder_quantity: 10,
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
  const { confirm } = useConfirm()
  const [sp] = useSearchParams()
  const lowStockOnly = sp.get('low_stock') === '1'
  const [form, setForm] = useState(empty)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [scan, setScan] = useState('')
  const [scanMsg, setScanMsg] = useState<string | null>(null)
  const [wasteItemId, setWasteItemId] = useState('')
  const [wasteQty, setWasteQty] = useState('1')
  const [wastePacks, setWastePacks] = useState('')
  const [wasteReason, setWasteReason] = useState('')
  const scanRef = useRef<HTMLInputElement>(null)

  const list = useQuery({
    queryKey: ['inventory', page, searchQ, lowStockOnly],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: '50',
      })
      if (searchQ) params.set('search', searchQ)
      return api.get<InventoryList>(`/api/inventory?${params}`)
    },
  })

  const categories = useQuery({
    queryKey: ['inventory-categories'],
    queryFn: () => api.get<string[] | { categories: string[] }>('/api/inventory/categories'),
  })

  const valuation = useQuery({
    queryKey: ['inventory-valuation'],
    queryFn: () =>
      api.get<{ total_value: number; total_on_hand: number; count: number }>(
        '/api/inventory/valuation',
      ),
  })

  const reorder = useQuery({
    queryKey: ['inventory-reorder'],
    queryFn: () =>
      api.get<{ suggestions: InventoryItem[]; count: number }>(
        '/api/inventory/reorder-suggestions',
      ),
  })
  const [reorderVendorId, setReorderVendorId] = useState('')
  const draftPos = useMutation({
    mutationFn: () =>
      api.post<{ created?: unknown[] }>('/api/inventory/reorder-suggestions/draft-pos', {
        vendor_id: Number(reorderVendorId),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory-reorder'] })
      qc.invalidateQueries({ queryKey: ['vendor-pos'] })
    },
  })

  const categoryOptions = Array.isArray(categories.data)
    ? categories.data
    : categories.data?.categories || []

  const items = useMemo(() => {
    const all = normalizeList(list.data || [])
    if (!lowStockOnly) return all
    return all.filter((i) => i.quantity <= (i.reorder_level ?? i.min_level ?? 0))
  }, [list.data, lowStockOnly])

  const packHint =
    Number(form.pack_size) > 1
      ? `${Number(form.packs) || 0} packs × ${form.pack_size} = ${(Number(form.packs) || 0) * Number(form.pack_size)} pcs` +
        (Number(form.quantity) ? ` + ${form.quantity} loose` : '')
      : null

  const save = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {
        name: form.name,
        category: form.category,
        barcode: form.barcode.trim() || null,
        manufacturer_part_number: form.manufacturer_part_number.trim() || null,
        location: form.location.trim() || null,
        reorder_level: Number(form.reorder_level),
        reorder_quantity: Number(form.reorder_quantity),
        unit: form.unit,
        pack_size: Math.max(1, Number(form.pack_size) || 1),
        description: form.description.trim() || null,
      }
      if (form.sku.trim()) body.sku = form.sku.trim()
      if (form.min_level !== '') body.min_level = Number(form.min_level)
      if (form.max_level !== '') body.max_level = Number(form.max_level)
      if (editingId) {
        return api.put(`/api/inventory/${editingId}`, body, {
          reason: 'Inventory item updated',
        })
      }
      body.quantity = Number(form.quantity) || 0
      if (Number(form.packs) > 0) body.packs = Number(form.packs)
      if (Number(form.unit_cost) > 0) body.unit_cost = Number(form.unit_cost)
      return api.post('/api/inventory', body)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-reorder'] })
      qc.invalidateQueries({ queryKey: ['inventory-valuation'] })
      setForm(empty)
      setEditingId(null)
    },
  })

  function cancelEdit() {
    setEditingId(null)
    setForm(empty)
    save.reset()
  }

  const wastageM = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        inventory_id: Number(wasteItemId),
        reason: wasteReason.trim(),
      }
      if (wastePacks.trim()) body.packs = Number(wastePacks)
      else body.quantity = Number(wasteQty) || 0
      return api.post('/api/inventory/wastage', body, {
        reason: wasteReason.trim() || 'Wastage',
      })
    },
    onSuccess: () => {
      setWasteReason('')
      setWasteQty('1')
      setWastePacks('')
      qc.invalidateQueries({ queryKey: ['inventory'] })
      qc.invalidateQueries({ queryKey: ['inventory-valuation'] })
      qc.invalidateQueries({ queryKey: ['inventory-transactions'] })
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
          ...empty,
          name: data.item.name,
          category: data.item.category,
          sku: data.item.sku || data.item.part_number || '',
          barcode: data.item.barcode || '',
          manufacturer_part_number: data.item.manufacturer_part_number || '',
          quantity: data.item.quantity,
          unit: data.item.unit || 'pcs',
          pack_size: data.item.pack_size || 1,
          unit_cost: Number(data.item.avg_cost || 0),
          location: data.item.location || '',
          reorder_level: data.item.reorder_level || 5,
          reorder_quantity: data.item.reorder_quantity || 10,
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
          <Field label="SKU (shop code)">
            <input
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
              placeholder={editingId ? undefined : 'Blank = auto PN001…'}
            />
          </Field>
          <Field label="Barcode (optional)">
            <input
              value={form.barcode}
              onChange={(e) => setForm({ ...form, barcode: e.target.value })}
              placeholder="Leave blank if none"
            />
          </Field>
          <Field label="Manufacturer part # (optional)">
            <input
              value={form.manufacturer_part_number}
              onChange={(e) =>
                setForm({ ...form, manufacturer_part_number: e.target.value })
              }
              placeholder="Leave blank if none"
            />
          </Field>
          <UnitSelect
            value={form.unit}
            onChange={(unit) => setForm({ ...form, unit })}
            required
          />
          <Field label="Pack size (pcs per pack)">
            <input
              type="number"
              min={1}
              value={form.pack_size}
              onChange={(e) => setForm({ ...form, pack_size: Number(e.target.value) || 1 })}
            />
          </Field>
          {!editingId ? (
            <>
              <Field label="Opening packs">
                <input
                  type="number"
                  min={0}
                  value={form.packs}
                  onChange={(e) => setForm({ ...form, packs: Number(e.target.value) || 0 })}
                />
              </Field>
              <Field label="Opening loose pcs">
                <input
                  type="number"
                  min={0}
                  value={form.quantity}
                  onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })}
                />
              </Field>
              <Field label="Unit cost (opening)">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.unit_cost}
                  onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })}
                />
              </Field>
            </>
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
          <Field label="Reorder qty">
            <input
              type="number"
              value={form.reorder_quantity}
              onChange={(e) =>
                setForm({ ...form, reorder_quantity: Number(e.target.value) })
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
          <Field label="Storage location">
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
          <div className="row-actions">
            <button className="btn" type="submit" disabled={save.isPending}>
              {editingId ? 'Update' : 'Create'}
            </button>
            {editingId ? (
              <button
                type="button"
                className="btn btn-secondary"
                disabled={save.isPending}
                onClick={cancelEdit}
              >
                Cancel
              </button>
            ) : null}
          </div>
        </FormGrid>
        {packHint ? <p className="muted">{packHint}</p> : null}
        {editingId ? (
          <p className="muted">
            Stock changes use Adjust / Wastage / PO receive — not this form. Cancel discards edits.
          </p>
        ) : (
          <p className="muted">
            Leave SKU blank to auto-assign PN001… Opening packs × pack size + loose pcs posts as a
            confirmed opening movement.
          </p>
        )}
      </Panel>

      <Panel title="Wastage / scrap">
        {wastageM.error ? <ErrorBox error={wastageM.error} /> : null}
        <FormGrid
          onSubmit={(e) => {
            e.preventDefault()
            if (!wasteItemId || !wasteReason.trim()) return
            wastageM.mutate()
          }}
        >
          <Field label="Item id">
            <input
              value={wasteItemId}
              onChange={(e) => setWasteItemId(e.target.value)}
              placeholder="Inventory id"
            />
          </Field>
          <Field label="Pieces">
            <input
              type="number"
              min={1}
              value={wasteQty}
              onChange={(e) => setWasteQty(e.target.value)}
            />
          </Field>
          <Field label="Or packs">
            <input
              type="number"
              min={0}
              value={wastePacks}
              onChange={(e) => setWastePacks(e.target.value)}
              placeholder="Uses item pack size"
            />
          </Field>
          <Field label="Reason">
            <input
              required
              value={wasteReason}
              onChange={(e) => setWasteReason(e.target.value)}
              placeholder="Damaged / expired / scrap"
            />
          </Field>
          <button
            className="btn btn-secondary"
            type="submit"
            disabled={wastageM.isPending || !wasteItemId || !wasteReason.trim()}
          >
            Record wastage
          </button>
        </FormGrid>
      </Panel>

      {(reorder.data?.suggestions || []).length > 0 ? (
        <Panel title={`Reorder suggestions (${reorder.data?.count})`}>
          <ul>
            {(reorder.data?.suggestions || []).slice(0, 8).map((s) => (
              <li key={s.id}>
                {s.name} — avail {s.available ?? s.quantity} / min{' '}
                {s.min_level ?? s.reorder_level}
                {s.preferred_vendor_id ? ` · vendor #${s.preferred_vendor_id}` : ''}
              </li>
            ))}
          </ul>
          <FormGrid
            onSubmit={(e: FormEvent) => {
              e.preventDefault()
              draftPos.mutate()
            }}
          >
            <Field label="Vendor id for draft POs">
              <input
                required
                value={reorderVendorId}
                onChange={(e) => setReorderVendorId(e.target.value)}
                placeholder="permanent vendor id"
              />
            </Field>
            <button
              className="btn"
              type="submit"
              disabled={draftPos.isPending || !reorderVendorId}
            >
              Create draft POs
            </button>
          </FormGrid>
          {draftPos.error ? <ErrorBox error={draftPos.error} /> : null}
          {draftPos.isSuccess ? (
            <p className="muted">
              Draft POs created — open Vendors to approve / order / receive.
            </p>
          ) : null}
        </Panel>
      ) : null}

      <Panel
        title="Stock"
        actions={
          valuation.data ? (
            <span className="muted">
              Value{' '}
              <strong className="num">
                {Number(valuation.data.total_value || 0).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                PKR
              </strong>
            </span>
          ) : null
        }
      >
        <form
          className="row-actions"
          style={{ marginBottom: 12 }}
          onSubmit={(e) => {
            e.preventDefault()
            setPage(1)
            setSearchQ(search.trim())
          }}
        >
          <input
            className="input"
            style={{ minWidth: '14rem', flex: 1 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, SKU, barcode…"
            aria-label="Search inventory"
          />
          <button type="submit" className="btn btn-secondary btn-sm">
            Search
          </button>
          {searchQ ? (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSearch('')
                setSearchQ('')
                setPage(1)
              }}
            >
              Clear
            </button>
          ) : null}
        </form>
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && items.length === 0 ? <Empty /> : null}
        {items.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>SKU</th>
                  <th>On hand</th>
                  <th>Packs</th>
                  <th>Reserved</th>
                  <th>Avail</th>
                  <th>Avg cost</th>
                  <th>Value</th>
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
                      <div className="muted">{item.category}</div>
                    </td>
                    <td>
                      {item.sku ||
                        item.part_number ||
                        item.manufacturer_part_number ||
                        item.barcode ||
                        '—'}
                    </td>
                    <td className="num">
                      {item.on_hand ?? item.quantity} {item.unit || 'pcs'}
                    </td>
                    <td className="num">
                      {(item.pack_size || 1) > 1
                        ? `${item.packs_on_hand ?? 0}+${item.loose_pieces ?? 0}`
                        : '—'}
                    </td>
                    <td className="num">{item.reserved ?? 0}</td>
                    <td className="num">{item.available ?? item.quantity}</td>
                    <td className="num">{Number(item.avg_cost || 0).toFixed(2)}</td>
                    <td className="num">{Number(item.stock_value || 0).toFixed(2)}</td>
                    <td>{item.location || '—'}</td>
                    <td className="row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setEditingId(item.id)
                          setWasteItemId(String(item.id))
                          setForm({
                            ...empty,
                            name: item.name,
                            category: item.category,
                            sku: item.sku || item.part_number || '',
                            barcode: item.barcode || '',
                            manufacturer_part_number:
                              item.manufacturer_part_number || '',
                            quantity: item.quantity,
                            unit: item.unit || 'pcs',
                            pack_size: item.pack_size || 1,
                            unit_cost: Number(item.avg_cost || 0),
                            location: item.location || '',
                            reorder_level: item.reorder_level || 5,
                            reorder_quantity: item.reorder_quantity || 10,
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
                        onClick={async () => {
                          if (
                            await confirm({
                              message: 'Delete this inventory item?',
                              danger: true,
                              confirmLabel: 'Delete',
                            })
                          ) {
                            remove.mutate(item.id)
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

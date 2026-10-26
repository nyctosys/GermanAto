import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, PageHeader, Panel } from '../components/ui'

type Tx = {
  id: number
  inventory_id?: number
  item_name?: string
  inventory_name?: string
  inventory_part_number?: string
  transaction_type?: string
  quantity?: number
  reference?: string
  reference_description?: string
  notes?: string
  reason?: string
  created_at?: string
  created_by_username?: string
}

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'po_receive', label: 'PO receive' },
  { value: 'opening', label: 'Opening' },
  { value: 'issue_to_ro', label: 'Issue to RO' },
  { value: 'return_from_ro', label: 'Return from RO' },
  { value: 'reserve', label: 'Reserve' },
  { value: 'release', label: 'Release' },
  { value: 'wastage', label: 'Wastage' },
  { value: 'adjustment', label: 'Adjustment' },
  { value: 'in', label: 'All inbound' },
  { value: 'out', label: 'All outbound' },
]

export function InventoryHistoryPage() {
  const [type, setType] = useState('')
  const q = useQuery({
    queryKey: ['inventory-transactions', type],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (type) params.set('transaction_type', type)
      const data = await api.get<{ transactions?: Tx[] } | Tx[]>(
        `/api/inventory/transactions?${params}`,
      )
      return Array.isArray(data) ? data : data.transactions || []
    },
  })

  return (
    <div>
      <PageHeader
        title="Inventory history"
        actions={
          <Link className="btn btn-secondary" to="/inventory">
            Back to inventory
          </Link>
        }
      />
      <Panel
        title="Movements"
        actions={
          <select
            className="select"
            value={type}
            onChange={(e) => setType(e.target.value)}
            aria-label="Filter by movement type"
          >
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value || 'all'} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        }
      >
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {!q.isLoading && !(q.data || []).length ? <Empty>No movements yet</Empty> : null}
        {(q.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Item</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>By</th>
                  <th>Reference</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((tx) => (
                  <tr key={tx.id}>
                    <td>{tx.created_at || '—'}</td>
                    <td>
                      {tx.item_name || tx.inventory_name || tx.inventory_id || '—'}
                      {tx.inventory_part_number ? (
                        <div className="muted">{tx.inventory_part_number}</div>
                      ) : null}
                    </td>
                    <td>{tx.transaction_type || '—'}</td>
                    <td className="num">{tx.quantity ?? '—'}</td>
                    <td>{tx.created_by_username || '—'}</td>
                    <td>{tx.reference || tx.reference_description || '—'}</td>
                    <td>{tx.notes || tx.reason || '—'}</td>
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

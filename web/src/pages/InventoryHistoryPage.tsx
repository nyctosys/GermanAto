import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, PageHeader, Panel } from '../components/ui'

type Tx = {
  id: number
  inventory_id?: number
  item_name?: string
  transaction_type?: string
  quantity?: number
  reference?: string
  notes?: string
  created_at?: string
}

export function InventoryHistoryPage() {
  const [type, setType] = useState('')
  const q = useQuery({
    queryKey: ['inventory-transactions', type],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (type) params.set('type', type)
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
        title="Transactions"
        actions={
          <select
            className="select"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">All types</option>
            <option value="in">In</option>
            <option value="out">Out</option>
            <option value="adjust">Adjust</option>
            <option value="restock">Restock</option>
          </select>
        }
      >
        {q.isLoading ? <Loading /> : null}
        {q.error ? <ErrorBox error={q.error} /> : null}
        {!q.isLoading && !(q.data || []).length ? <Empty /> : null}
        {(q.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Item</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Reference</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {(q.data || []).map((tx) => (
                  <tr key={tx.id}>
                    <td>{tx.created_at || '—'}</td>
                    <td>{tx.item_name || tx.inventory_id || '—'}</td>
                    <td>{tx.transaction_type || '—'}</td>
                    <td>{tx.quantity ?? '—'}</td>
                    <td>{tx.reference || '—'}</td>
                    <td>{tx.notes || '—'}</td>
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

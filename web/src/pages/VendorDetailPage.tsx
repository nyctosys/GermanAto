import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  Money,
  PageHeader,
  Panel,
} from '../components/ui'

export function VendorDetailPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [ledgerForm, setLedgerForm] = useState({
    amount: 0,
    description: '',
    entry_type: 'debit',
    date: new Date().toISOString().slice(0, 10),
  })
  const [poForm, setPoForm] = useState({
    description: '',
    amount: 0,
    status: 'pending',
  })

  const vendor = useQuery({
    queryKey: ['vendor', id],
    enabled: !!id,
    queryFn: () => api.get<Record<string, unknown>>(`/api/vendors/${id}`),
  })

  const ledger = useQuery({
    queryKey: ['vendor-ledger', id],
    enabled: !!id,
    queryFn: async () => {
      const data = await api.get<{ entries?: Record<string, unknown>[] } | Record<string, unknown>[]>(
        `/api/vendors/${id}/ledger`,
      )
      return Array.isArray(data) ? data : data.entries || []
    },
  })

  const pos = useQuery({
    queryKey: ['vendor-pos', id],
    enabled: !!id,
    queryFn: async () => {
      const data = await api.get<
        { purchase_orders?: Record<string, unknown>[] } | Record<string, unknown>[]
      >(`/api/vendors/${id}/purchase-orders`)
      return Array.isArray(data) ? data : data.purchase_orders || []
    },
  })

  const addLedger = useMutation({
    mutationFn: () =>
      api.post('/api/ledger/add', {
        vendor_id: Number(id),
        ...ledgerForm,
        amount: Number(ledgerForm.amount),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendor-ledger', id] })
      setLedgerForm({
        amount: 0,
        description: '',
        entry_type: 'debit',
        date: new Date().toISOString().slice(0, 10),
      })
    },
  })

  const addPo = useMutation({
    mutationFn: () =>
      api.post('/api/purchase-orders/add', {
        vendor_id: Number(id),
        ...poForm,
        amount: Number(poForm.amount),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['vendor-pos', id] })
      setPoForm({ description: '', amount: 0, status: 'pending' })
    },
  })

  if (vendor.isLoading) return <Loading />
  if (vendor.error) return <ErrorBox error={vendor.error} />

  const v = vendor.data || {}

  return (
    <div>
      <PageHeader
        title={String(v.name || `Vendor #${id}`)}
        actions={
          <Link className="btn btn-secondary" to="/vendors">
            Back
          </Link>
        }
      />
      <Panel title="Details">
        <p>
          {String(v.company_name || '')} · {String(v.phone || '')} ·{' '}
          {String(v.email || '')}
        </p>
        <p className="muted">{String(v.address || '')}</p>
      </Panel>

      <Panel title="Add ledger entry">
        {addLedger.error ? <ErrorBox error={addLedger.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addLedger.mutate()
          }}
        >
          <Field label="Date">
            <input
              type="date"
              value={ledgerForm.date}
              onChange={(e) => setLedgerForm({ ...ledgerForm, date: e.target.value })}
            />
          </Field>
          <Field label="Type">
            <select
              value={ledgerForm.entry_type}
              onChange={(e) => setLedgerForm({ ...ledgerForm, entry_type: e.target.value })}
            >
              <option value="debit">Debit</option>
              <option value="credit">Credit</option>
            </select>
          </Field>
          <Field label="Amount">
            <input
              type="number"
              step="0.01"
              value={ledgerForm.amount}
              onChange={(e) =>
                setLedgerForm({ ...ledgerForm, amount: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Description">
            <input
              value={ledgerForm.description}
              onChange={(e) =>
                setLedgerForm({ ...ledgerForm, description: e.target.value })
              }
            />
          </Field>
          <button className="btn" type="submit">
            Add
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Ledger">
        {ledger.isLoading ? <Loading /> : null}
        {!ledger.isLoading && !(ledger.data || []).length ? <Empty /> : null}
        {(ledger.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(ledger.data || []).map((row, idx) => (
                  <tr key={Number(row.id) || idx}>
                    <td>{String(row.date || '')}</td>
                    <td>{String(row.entry_type || row.type || '')}</td>
                    <td>{String(row.description || '')}</td>
                    <td>
                      <Money value={Number(row.amount || 0)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>

      <Panel title="Add purchase order">
        {addPo.error ? <ErrorBox error={addPo.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            addPo.mutate()
          }}
        >
          <Field label="Description">
            <input
              value={poForm.description}
              onChange={(e) => setPoForm({ ...poForm, description: e.target.value })}
            />
          </Field>
          <Field label="Amount">
            <input
              type="number"
              step="0.01"
              value={poForm.amount}
              onChange={(e) => setPoForm({ ...poForm, amount: Number(e.target.value) })}
            />
          </Field>
          <button className="btn" type="submit">
            Add PO
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Purchase orders">
        {!pos.isLoading && !(pos.data || []).length ? <Empty /> : null}
        {(pos.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(pos.data || []).map((row, idx) => (
                  <tr key={Number(row.id) || idx}>
                    <td>{String(row.id || '')}</td>
                    <td>{String(row.description || '')}</td>
                    <td>
                      <Money value={Number(row.amount || 0)} />
                    </td>
                    <td>{String(row.status || '')}</td>
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

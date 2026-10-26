import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, PageHeader } from '../components/ui'
import { InvoiceDocumentForm } from './InvoiceDocumentForm'
import { emptyInvoiceForm, toPayload } from './invoiceTypes'

export function InvoiceCreatePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyInvoiceForm)
  const create = useMutation({
    mutationFn: () => api.post<{ invoice_id: number }>('/api/add', toPayload(form, 'Invoice')),
    onSuccess: (data) => navigate(`/invoices/${data.invoice_id}/edit`),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }

  return (
    <div>
      <PageHeader
        title="New invoice"
        actions={
          <Link className="btn btn-secondary" to="/invoices">
            ← Invoices
          </Link>
        }
      />
      {create.error ? <ErrorBox error={create.error} /> : null}
      <InvoiceDocumentForm
        title="Customer & vehicle"
        form={form}
        setForm={setForm}
        onSubmit={onSubmit}
        busy={create.isPending}
        submitLabel="Create invoice"
        cancelTo="/invoices"
      />
    </div>
  )
}

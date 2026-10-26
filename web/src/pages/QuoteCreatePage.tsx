import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, PageHeader } from '../components/ui'
import { InvoiceDocumentForm } from './InvoiceDocumentForm'
import { emptyInvoiceForm, toPayload } from './invoiceTypes'

export function QuoteCreatePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyInvoiceForm)
  const create = useMutation({
    mutationFn: () => api.post<{ invoice_id: number }>('/api/add', toPayload(form, 'Quote')),
    onSuccess: () => navigate('/quotes/pending'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }

  return (
    <div>
      <PageHeader title="New quote" />
      {create.error ? <ErrorBox error={create.error} /> : null}
      <InvoiceDocumentForm
        title="Customer & vehicle"
        form={form}
        setForm={setForm}
        onSubmit={onSubmit}
        busy={create.isPending}
        showAdvance={false}
        showEstimateMeta
        submitLabel="Create estimate"
      />
    </div>
  )
}

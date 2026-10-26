import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Loading, PageHeader } from '../components/ui'
import { InvoiceDocumentForm } from './InvoiceDocumentForm'
import { emptyInvoiceForm, toPayload, type InvoiceFormState } from './invoiceTypes'

type InvoiceDetail = {
  id: number
  document_no?: string | null
  customer_id?: number | null
  car_id?: number | null
  customer_name: string
  customer_address: string
  customer_phone: string
  customer_reg_no: string
  customer_made: string
  customer_mileage: string
  customer_vin?: string
  customer_color?: string
  customer_chasis?: string
  advance?: number
  discount?: number
  include_tax?: boolean
  locked?: boolean
  locked_at?: string | null
  status?: string
  items?: { product_name: string; part_number?: string; quantity: number; price: number }[]
  labours?: { description: string; price: number }[]
}

export function InvoiceEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState<InvoiceFormState>(emptyInvoiceForm())

  const detail = useQuery({
    queryKey: ['invoice', id],
    enabled: !!id,
    queryFn: () => api.get<InvoiceDetail | { invoice: InvoiceDetail }>(`/api/invoice/${id}`),
  })

  const inv: InvoiceDetail | undefined = detail.data
    ? 'invoice' in detail.data
      ? detail.data.invoice
      : detail.data
    : undefined
  const locked = !!(inv?.locked || inv?.locked_at)

  useEffect(() => {
    if (!inv) return
    setForm({
      customer_id: inv.customer_id || null,
      car_id: inv.car_id || null,
      customer_name: inv.customer_name || '',
      customer_address: inv.customer_address || '',
      customer_phone: inv.customer_phone || '',
      customer_reg_no: inv.customer_reg_no || '',
      customer_made: inv.customer_made || '',
      customer_mileage: inv.customer_mileage || '',
      customer_vin: inv.customer_vin || '',
      customer_color: inv.customer_color || '',
      customer_chasis: inv.customer_chasis || '',
      advance: inv.advance || 0,
      discount: inv.discount || 0,
      include_tax: !!inv.include_tax,
      items: (inv.items || []).map((i) => ({
        product_name: i.product_name,
        part_number: i.part_number || '',
        quantity: i.quantity,
        price: i.price,
      })),
      labours: (inv.labours || []).map((l) => ({
        description: l.description,
        price: l.price,
      })),
    })
  }, [inv])

  const save = useMutation({
    mutationFn: () =>
      api.put(`/api/invoice/${id}/update`, toPayload(form, 'Invoice')),
    onSuccess: () => navigate('/invoices'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (locked) return
    save.mutate()
  }

  if (detail.isLoading) return <Loading />
  if (detail.error) return <ErrorBox error={detail.error} />

  const title = locked
    ? `View ${inv?.document_no || `invoice #${id}`}`
    : `Edit ${inv?.document_no || `invoice #${id}`}`

  return (
    <div>
      <PageHeader
        title={title}
        actions={
          <Link className="btn btn-secondary" to="/invoices">
            ← Invoices
          </Link>
        }
      />
      {locked ? (
        <p className="muted" style={{ marginBottom: 12 }}>
          This invoice is locked because a payment was recorded (partial or full). Use a credit
          note for adjustments, or record further payments from the invoices list.
        </p>
      ) : null}
      {save.error ? <ErrorBox error={save.error} /> : null}
      <InvoiceDocumentForm
        title="Customer & vehicle"
        form={form}
        setForm={setForm}
        onSubmit={onSubmit}
        busy={save.isPending}
        submitLabel="Save changes"
        cancelTo="/invoices"
        readOnly={locked}
        footerNote={
          locked ? (
            <span className="muted">
              Status: {inv?.status || '—'}
              {inv?.locked_at ? ` · Locked ${inv.locked_at}` : ''}
            </span>
          ) : null
        }
      />
    </div>
  )
}

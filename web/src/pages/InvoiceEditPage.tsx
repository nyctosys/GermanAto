import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Loading, PageHeader } from '../components/ui'
import { InvoiceDocumentForm } from './InvoiceDocumentForm'
import { emptyInvoiceForm, toPayload, type InvoiceFormState } from './invoiceTypes'

type InvoiceDetail = {
  id: number
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

  useEffect(() => {
    if (!detail.data) return
    const inv = 'invoice' in detail.data ? detail.data.invoice : detail.data
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
  }, [detail.data])

  const save = useMutation({
    mutationFn: () =>
      api.put(`/api/invoice/${id}/update`, toPayload(form, 'Invoice')),
    onSuccess: () => navigate('/invoices'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  if (detail.isLoading) return <Loading />
  if (detail.error) return <ErrorBox error={detail.error} />

  return (
    <div>
      <PageHeader title={`Edit invoice #${id}`} />
      {save.error ? <ErrorBox error={save.error} /> : null}
      <InvoiceDocumentForm
        title="Customer & vehicle"
        form={form}
        setForm={setForm}
        onSubmit={onSubmit}
        busy={save.isPending}
        submitLabel="Save changes"
      />
    </div>
  )
}

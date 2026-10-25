export type LineItem = {
  product_name: string
  part_number: string
  quantity: number
  price: number
}

export type LabourLine = {
  description: string
  price: number
}

export type InvoiceFormState = {
  customer_id: number | null
  car_id: number | null
  customer_name: string
  customer_address: string
  customer_phone: string
  customer_reg_no: string
  customer_made: string
  customer_mileage: string
  customer_vin: string
  customer_color: string
  customer_chasis: string
  advance: number
  discount: number
  include_tax: boolean
  items: LineItem[]
  labours: LabourLine[]
}

export const emptyInvoiceForm = (): InvoiceFormState => ({
  customer_id: null,
  car_id: null,
  customer_name: '',
  customer_address: '',
  customer_phone: '',
  customer_reg_no: '',
  customer_made: '',
  customer_mileage: '',
  customer_vin: '',
  customer_color: '',
  customer_chasis: '',
  advance: 0,
  discount: 0,
  include_tax: false,
  items: [{ product_name: '', part_number: '', quantity: 1, price: 0 }],
  labours: [],
})

export function calcNet(form: InvoiceFormState) {
  const items = form.items.reduce((s, i) => s + Number(i.quantity) * Number(i.price), 0)
  const labour = form.labours.reduce((s, l) => s + Number(l.price), 0)
  return items + labour
}

export function toPayload(form: InvoiceFormState, typeOf: 'Invoice' | 'Quote') {
  const net = calcNet(form)
  const tax = form.include_tax ? net * 0.17 : 0
  const total = form.include_tax ? net + tax : net
  return {
    ...form,
    type_of: typeOf,
    items: form.items.filter((i) => i.product_name && i.quantity > 0),
    labours: form.labours.filter((l) => l.description),
    tax_amount: tax,
    net_total: net,
    balance: Math.round((total - Number(form.discount) - Number(form.advance)) * 100) / 100,
  }
}

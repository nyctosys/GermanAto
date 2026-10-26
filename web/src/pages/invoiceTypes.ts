export type LineItem = {
  product_name: string
  part_number: string
  quantity: number
  price: number
  inventory_id?: number | null
  available?: number | null
}

export type LabourLine = {
  description: string
  price: number
  labour_code_id?: number | null
  std_hours?: number | null
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
  expected_duration_hours?: number | null
  expected_completion_at?: string
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
  expected_duration_hours: null,
  expected_completion_at: '',
  items: [{ product_name: '', part_number: '', quantity: 1, price: 0, inventory_id: null, available: null }],
  labours: [],
})

export function calcNet(form: InvoiceFormState) {
  const items = form.items.reduce((s, i) => s + Number(i.quantity) * Number(i.price), 0)
  const labour = form.labours.reduce((s, l) => s + Number(l.price), 0)
  return items + labour
}

export function calcDurationHours(form: InvoiceFormState) {
  return form.labours.reduce((s, l) => s + Number(l.std_hours || 0), 0)
}

export function missingParts(form: InvoiceFormState) {
  return form.items
    .filter((i) => i.inventory_id && i.available != null && Number(i.quantity) > Number(i.available))
    .map((i) => ({
      ...i,
      missing: Number(i.quantity) - Number(i.available || 0),
    }))
}

export function toPayload(form: InvoiceFormState, typeOf: 'Invoice' | 'Quote') {
  const net = calcNet(form)
  const tax = form.include_tax ? net * 0.17 : 0
  const total = form.include_tax ? net + tax : net
  const duration = form.expected_duration_hours ?? calcDurationHours(form)
  return {
    ...form,
    type_of: typeOf,
    items: form.items
      .filter((i) => i.product_name && i.quantity > 0)
      .map((i) => ({
        product_name: i.product_name,
        part_number: i.part_number,
        quantity: i.quantity,
        price: i.price,
        inventory_id: i.inventory_id || undefined,
      })),
    labours: form.labours
      .filter((l) => l.description)
      .map((l) => ({
        description: l.description,
        price: l.price,
        labour_code_id: l.labour_code_id || undefined,
        std_hours: l.std_hours || undefined,
      })),
    tax_amount: tax,
    net_total: net,
    expected_duration_hours: duration || null,
    expected_completion_at: form.expected_completion_at || null,
    // Quotes: advance stays 0 — deposits are liabilities via CustomerDeposit
    advance: typeOf === 'Quote' ? 0 : Number(form.advance),
    balance: Math.round((total - Number(form.discount) - (typeOf === 'Quote' ? 0 : Number(form.advance))) * 100) / 100,
  }
}

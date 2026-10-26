import { api } from './client'

export type EntityType = 'customer' | 'car' | 'worker' | 'vendor' | 'inventory'

export type EntityHit = {
  id: number
  code?: string | null
  label: string
  entity_type: EntityType
  name?: string | null
  phone?: string | null
  address?: string | null
  plate_no?: string | null
  make?: string | null
  model?: string | null
  vin?: string | null
  mileage?: string | null
  color?: string | null
  chasis_no?: string | null
  customer_id?: number | null
  customer_name?: string | null
  customer_phone?: string | null
  customer_address?: string | null
  customer_code?: string | null
  company_name?: string | null
  part_number?: string | null
  barcode?: string | null
  available?: number
  price?: number
  avg_cost?: number
  unit?: string | null
  preferred_vendor_id?: number | null
  employee_id?: string | null
  position?: string | null
}

export type EntitySearchResult = {
  query: string
  type: EntityType
  results: EntityHit[]
  count: number
  did_you_mean?: string | null
  closest?: string[]
}

export type DuplicateCheckResult = {
  duplicate: boolean
  matches: EntityHit[]
  warnings: string[]
  message?: string | null
}

export type CustomerActivity = {
  receivable_total?: number
  open_invoice_count?: number
  open_invoices?: Array<Record<string, unknown>>
  recent_invoices?: Array<Record<string, unknown>>
  recent_estimates?: Array<Record<string, unknown>>
  recent_repairs?: Array<Record<string, unknown>>
  counts?: {
    invoices?: number
    estimates?: number
    repairs?: number
    vehicles?: number
  }
}

export type CustomerBundle = {
  customer: EntityHit & {
    alternate_phone?: string | null
    customer_type?: string | null
    notes?: string | null
    consent_whatsapp?: boolean
    consent_sms?: boolean
    consent_call?: boolean
  }
  vehicles: EntityHit[]
  count: number
  activity?: CustomerActivity
}

export function searchEntities(
  type: EntityType,
  q: string,
  opts?: { limit?: number; customerId?: number | null },
) {
  const params = new URLSearchParams()
  params.set('type', type)
  params.set('q', q)
  if (opts?.limit) params.set('limit', String(opts.limit))
  if (opts?.customerId) params.set('customer_id', String(opts.customerId))
  return api.get<EntitySearchResult>(`/api/entities/search?${params}`)
}

export function getCustomerBundle(customerId: number) {
  return api.get<CustomerBundle>(`/api/entities/customers/${customerId}`)
}

export function checkDuplicate(
  type: EntityType,
  fields: Record<string, unknown>,
) {
  return api.post<DuplicateCheckResult>('/api/entities/check-duplicate', {
    type,
    ...fields,
  })
}

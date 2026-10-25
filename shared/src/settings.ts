import { z } from 'zod'

export const WorkshopSettingsSchema = z.object({
  discount_approval_pct: z.number().min(0).max(100),
  mandatory_receipt_amount: z.number().min(0),
  comeback_window_days: z.number().int().min(0),
  payment_gate_enabled: z.boolean(),
  expense_heads: z.array(z.string().min(1)),
})

export type WorkshopSettings = z.infer<typeof WorkshopSettingsSchema>

export const GRANULAR_PERMISSIONS = [
  'approve_discount',
  'override_payment_gate',
  'qc_signoff',
  'adjust_stock',
  'reopen_period',
  'approve_evidence_exception',
] as const

export type GranularPermission = (typeof GRANULAR_PERMISSIONS)[number]

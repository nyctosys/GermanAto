import { z } from 'zod'

export const AdvancePolicySchema = z.object({
  mode: z.enum(['none', 'fixed', 'percent', 'full', 'custom']),
  fixed_amount: z.number().min(0).default(0),
  percent: z.number().min(0).max(100).default(50),
  allow_authorized_custom: z.boolean().default(true),
})

export const WorkshopSettingsSchema = z.object({
  discount_approval_pct: z.number().min(0).max(100),
  mandatory_receipt_amount: z.number().min(0),
  comeback_window_days: z.number().int().min(0),
  payment_gate_enabled: z.boolean(),
  expense_heads: z.array(z.string().min(1)),
  advance_policy: AdvancePolicySchema.optional(),
  estimate_notify_channels: z.array(z.string().min(1)).optional(),
  variation_requires_approval: z.boolean().optional(),
  assignment_notify_channels: z.array(z.string().min(1)).optional(),
})

export type WorkshopSettings = z.infer<typeof WorkshopSettingsSchema>

export const GRANULAR_PERMISSIONS = [
  'approve_discount',
  'override_payment_gate',
  'qc_signoff',
  'adjust_stock',
  'reopen_period',
  'approve_evidence_exception',
  'override_assignment_conflict',
] as const

export type GranularPermission = (typeof GRANULAR_PERMISSIONS)[number]

import { z } from 'zod'

export const payTypeSchema = z.enum(['customer', 'warranty', 'internal'])

export const jobCardLineSchema = z.object({
  line_type: z.enum(['labour', 'part']),
  labour_code_id: z.number().int().positive().optional().nullable(),
  inventory_id: z.number().int().positive().optional().nullable(),
  description: z.string().min(1),
  quantity: z.number().int().nonnegative(),
  unit_price: z.number().nonnegative(),
  std_hours: z.number().nonnegative().optional().nullable(),
  pay_type: payTypeSchema.default('customer'),
  assigned_technician: z.string().optional().nullable(),
  line_status: z
    .enum(['Pending', 'Approved', 'Rejected', 'In progress', 'Done', 'QC passed'])
    .default('Pending'),
})

export const lineDecisionSchema = z.object({
  kind: z.enum(['item', 'labour']),
  id: z.number().int().positive(),
  decision: z.enum(['approved', 'rejected']),
  media_data_url: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
})

export const depositCreateSchema = z.object({
  amount: z.number().positive(),
  visit_id: z.number().int().positive().optional().nullable(),
  customer_id: z.number().int().positive().optional().nullable(),
  quote_invoice_id: z.number().int().positive().optional().nullable(),
  evidence_attachment_id: z.number().int().positive(),
})

export const gatePassSchema = z.object({
  old_parts_checklist: z.array(z.record(z.string(), z.unknown())).default([]),
  exit_odometer: z.string().optional().nullable(),
  photos: z.array(z.unknown()).default([]),
  payment_gate_bypass: z.boolean().optional(),
  reason: z.string().optional().nullable(),
  invoice_id: z.number().int().positive().optional().nullable(),
})

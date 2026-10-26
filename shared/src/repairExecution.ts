import { z } from 'zod'

export const repairTimeRecordSchema = z.object({
  hours: z.number().positive().max(24),
  notes: z.string().optional().nullable(),
})

export const partsRequestSchema = z.object({
  inventory_id: z.number().int().positive().optional().nullable(),
  description: z.string().optional(),
  quantity: z.number().int().positive().default(1),
  bill_customer: z.boolean().default(false),
  ownership_type: z.enum(['shop_stock', 'customer_supplied']).default('shop_stock'),
  part_number: z.string().optional().nullable(),
})

export const partsIssueSchema = z.object({
  qty: z.number().int().positive().optional(),
  quantity: z.number().int().positive().optional(),
  from_reserve: z.boolean().optional().nullable(),
})

export const faultRecordSchema = z.object({
  description: z.string().min(1),
  severity: z.enum(['low', 'normal', 'high', 'critical']).default('normal'),
  estimated_price: z.number().nonnegative().optional(),
  labour_code_id: z.number().int().positive().optional().nullable(),
  photo_attachment_id: z.number().int().positive().optional().nullable(),
  lines: z
    .array(
      z.object({
        line_type: z.enum(['labour', 'part']).default('labour'),
        description: z.string().min(1),
        quantity: z.number().int().positive().default(1),
        unit_price: z.number().nonnegative().default(0),
        labour_code_id: z.number().int().positive().optional().nullable(),
        inventory_id: z.number().int().positive().optional().nullable(),
      }),
    )
    .optional(),
})

export const submitInspectionSchema = z.object({
  notes: z.string().optional().nullable(),
})

import { z } from 'zod'

export const OwnershipTypeSchema = z.enum(['shop_stock', 'customer_supplied'])

export const StockMovementTypeSchema = z.enum([
  'po_receive',
  'reserve',
  'release',
  'issue_to_ro',
  'return_from_ro',
  'adjustment',
])

export const PoStatusSchema = z.enum([
  'draft',
  'ordered',
  'partial',
  'received',
  'closed',
])

export const InventoryCreateSchema = z.object({
  name: z.string().min(1),
  category: z.string().min(1),
  barcode: z.string().optional().nullable(),
  manufacturer_part_number: z.string().optional().nullable(),
  quantity: z.number().int().min(0).default(0),
  reorder_level: z.number().int().min(0).optional(),
  min_level: z.number().int().min(0).optional().nullable(),
  max_level: z.number().int().min(0).optional().nullable(),
  location: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  alternate_codes: z.string().optional().nullable(),
  pending_purchase: z.boolean().optional(),
})

export const StockAdjustSchema = z.object({
  inventory_id: z.number().int().positive(),
  delta: z.number().int().refine((n) => n !== 0, 'delta cannot be zero'),
  reason: z.string().min(1),
  evidence_path: z.string().min(1),
})

export const PoReceiveSchema = z.object({
  quantity: z.number().int().positive(),
  unit_cost: z.number().min(0),
  inventory_id: z.number().int().positive().optional(),
  receipt_attachment_path: z.string().min(1).optional(),
})

export type InventoryCreate = z.infer<typeof InventoryCreateSchema>
export type StockAdjust = z.infer<typeof StockAdjustSchema>
export type PoReceive = z.infer<typeof PoReceiveSchema>

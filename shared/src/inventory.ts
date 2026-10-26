import { z } from 'zod'

export const OwnershipTypeSchema = z.enum(['shop_stock', 'customer_supplied'])

export const StockMovementTypeSchema = z.enum([
  'po_receive',
  'reserve',
  'release',
  'issue_to_ro',
  'return_from_ro',
  'adjustment',
  'wastage',
  'opening',
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
  sku: z.string().min(1).max(20).optional().nullable(),
  part_number: z.string().min(1).max(20).optional().nullable(),
  barcode: z.string().optional().nullable(),
  manufacturer_part_number: z.string().optional().nullable(),
  quantity: z.number().int().min(0).default(0),
  packs: z.number().int().min(0).optional(),
  pieces: z.number().int().min(0).optional(),
  unit: z.string().min(1).max(20).optional(),
  pack_size: z.number().int().min(1).default(1),
  valuation_method: z.enum(['avg']).optional(),
  preferred_vendor_id: z.number().int().positive().optional().nullable(),
  reorder_level: z.number().int().min(0).optional(),
  reorder_quantity: z.number().int().min(0).optional(),
  min_level: z.number().int().min(0).optional().nullable(),
  max_level: z.number().int().min(0).optional().nullable(),
  location: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  alternate_codes: z.string().optional().nullable(),
  pending_purchase: z.boolean().optional(),
  unit_cost: z.number().min(0).optional(),
})

export const StockAdjustSchema = z.object({
  inventory_id: z.number().int().positive(),
  delta: z.number().int().refine((n) => n !== 0, 'delta cannot be zero').optional(),
  packs: z.number().int().min(0).optional(),
  pieces: z.number().int().min(0).optional(),
  reason: z.string().min(1),
  evidence_path: z.string().min(1),
  allow_negative: z.boolean().optional(),
})

export const StockWastageSchema = z.object({
  inventory_id: z.number().int().positive(),
  quantity: z.number().int().positive().optional(),
  packs: z.number().int().min(0).optional(),
  pieces: z.number().int().min(0).optional(),
  reason: z.string().min(1),
  evidence_path: z.string().optional().nullable(),
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

import { z } from 'zod'
import { PkPhoneSchema, RegNoSchema } from './validation'

export const CustomerTypeSchema = z.enum([
  'retail',
  'fleet',
  'insurance',
  'corporate',
  'walk_in',
  'other',
])

export const CustomerFormSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(255),
  phone: PkPhoneSchema,
  alternate_phone: z
    .union([PkPhoneSchema, z.literal(''), z.null()])
    .optional()
    .transform((v) => (v === '' || v == null ? null : v)),
  address: z.string().trim().max(255).optional().nullable(),
  customer_type: CustomerTypeSchema.default('retail'),
  notes: z.string().trim().max(2000).optional().nullable(),
  consent_whatsapp: z.boolean().default(false),
  consent_sms: z.boolean().default(false),
  consent_call: z.boolean().default(true),
  force: z.boolean().optional(),
  version: z.number().int().optional(),
})

export const VehicleFormSchema = z.object({
  customer_id: z.number().int().positive().nullable().optional(),
  make: z.string().trim().max(100).optional().nullable(),
  model: z.string().trim().max(100).optional().nullable(),
  year: z.number().int().min(1950).max(2100).nullable().optional(),
  plate_no: z
    .union([RegNoSchema, z.literal(''), z.null()])
    .optional()
    .transform((v) => (v === '' || v == null ? null : v)),
  mileage: z.string().trim().max(50).optional().nullable(),
  vin: z.string().trim().max(17).optional().nullable(),
  color: z.string().trim().max(50).optional().nullable(),
  chasis_no: z.string().trim().max(50).optional().nullable(),
  engine_no: z.string().trim().max(50).optional().nullable(),
  notes: z.string().trim().max(2000).optional().nullable(),
  force_new: z.boolean().optional(),
  version: z.number().int().optional(),
})

export type CustomerForm = z.infer<typeof CustomerFormSchema>
export type VehicleForm = z.infer<typeof VehicleFormSchema>

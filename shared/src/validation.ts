import { z } from 'zod'

/** Pakistan mobile → E.164 (+923XXXXXXXXX) */
export const PkPhoneSchema = z
  .string()
  .trim()
  .transform((raw, ctx) => {
    let digits = raw.replace(/\D/g, '')
    if (digits.startsWith('0092')) digits = digits.slice(4)
    else if (digits.startsWith('92') && digits.length >= 12) digits = digits.slice(2)
    else if (digits.startsWith('0') && digits.length === 11) digits = digits.slice(1)
    if (digits.length !== 10 || !digits.startsWith('3')) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Enter a valid Pakistan mobile (03XX… or +923…)',
      })
      return z.NEVER
    }
    return `+92${digits}`
  })

export const RegNoSchema = z
  .string()
  .trim()
  .min(2)
  .max(20)
  .regex(/^[A-Za-z0-9\-\s]+$/, 'Invalid registration number')
  .transform((v) => v.toUpperCase().replace(/\s+/g, ' '))

export const CnicSchema = z
  .string()
  .trim()
  .transform((raw, ctx) => {
    const digits = raw.replace(/\D/g, '')
    if (digits.length !== 13) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'CNIC must be 13 digits',
      })
      return z.NEVER
    }
    return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`
  })

export const NonNegativeNumberSchema = z.number().nonnegative()
export const NonNegativeIntSchema = z.number().int().nonnegative()

import { z } from 'zod'

/** Integer paisa (1 PKR = 100 paisa). Never store money as float. */
export const PaisaSchema = z
  .number()
  .int('Amount must be whole paisa')
  .nonnegative('Amount must not be negative')

export const PositivePaisaSchema = PaisaSchema.positive('Amount must be greater than zero')

export function toPaisa(pkr: number): number {
  return Math.round(Number(pkr) * 100)
}

export function fromPaisa(paisa: number): number {
  return paisa / 100
}

export function formatPkr(paisa: number): string {
  return `${fromPaisa(paisa).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} PKR`
}

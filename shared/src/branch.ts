import { z } from 'zod'

/** 8-char lowercase hex branch id */
export const BranchIdSchema = z
  .string()
  .regex(/^[0-9a-f]{8}$/, 'branch_id must be 8 lowercase hex characters')

export const DEFAULT_BRANCH_ID = 'a1b2c3d4'

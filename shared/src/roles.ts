import { z } from 'zod'

export const RoleSchema = z.enum([
  'admin',
  'owner',
  'manager',
  'accountant',
  'service_advisor',
  'technician',
  'store_keeper',
  'inventory_manager',
])

export type Role = z.infer<typeof RoleSchema>

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Owner (admin)',
  owner: 'Owner',
  manager: 'Manager',
  accountant: 'Accountant',
  service_advisor: 'Service Advisor',
  technician: 'Technician',
  store_keeper: 'Store Keeper',
  inventory_manager: 'Store Keeper (legacy)',
}

export type NavItem = {
  label: string
  to: string
  permission: string
}

export type NavGroup = {
  group: string | null
  items: NavItem[]
}

/** Mirrors backend/static/js/app-shell.js destinations. */
export const NAV: NavGroup[] = [
  {
    group: null,
    items: [{ label: 'Dashboard', to: '/', permission: 'home' }],
  },
  {
    group: 'Create',
    items: [
      { label: 'New job card', to: '/job-cards/new', permission: 'repair-order' },
      { label: 'New invoice', to: '/invoices/new', permission: 'invoice' },
      { label: 'New quote', to: '/quotes/new', permission: 'invoice' },
      { label: 'New repair order', to: '/repair-orders/new', permission: 'repair-order' },
    ],
  },
  {
    group: 'Sales',
    items: [
      { label: 'Job cards', to: '/job-cards', permission: 'repair-order' },
      { label: 'Invoices', to: '/invoices', permission: 'invoice' },
      { label: 'Quotes', to: '/quotes/pending', permission: 'invoice' },
      { label: 'Repair orders', to: '/repair-orders', permission: 'repair-order' },
      { label: 'My jobs (work)', to: '/repair-execution', permission: 'repair-order' },
      { label: 'Labour codes', to: '/labour-codes', permission: 'repair-order' },
    ],
  },
  {
    group: 'Operations',
    items: [
      { label: 'Inventory', to: '/inventory', permission: 'inventory' },
      { label: 'Vendors', to: '/vendors', permission: 'vendors' },
      { label: 'Customers & vehicles', to: '/cars', permission: 'car' },
    ],
  },
  {
    group: 'Finance',
    items: [
      { label: 'Money In', to: '/money-in', permission: 'daily-expenses' },
      { label: 'Money Out', to: '/money-out', permission: 'daily-expenses' },
      { label: 'Daily expenses', to: '/finance/daily-expenses', permission: 'daily-expenses' },
      { label: 'Major expenses', to: '/finance/major-expenses', permission: 'major-expenses' },
      { label: 'Cash received', to: '/finance/cash-received', permission: 'daily-expenses' },
      { label: 'Monthly ledger', to: '/finance/monthly-ledger', permission: 'daily-expenses' },
      { label: 'Finance hub', to: '/finance', permission: 'daily-expenses' },
      { label: 'Reports', to: '/reports', permission: 'reports' },
    ],
  },
  {
    group: 'People',
    items: [
      { label: 'Employees', to: '/hr/employees', permission: 'hr' },
      { label: 'Attendance', to: '/hr/attendance', permission: 'hr' },
      { label: 'Salaries', to: '/hr/salaries', permission: 'hr' },
      { label: 'Devices', to: '/hr/devices', permission: 'hr' },
    ],
  },
  {
    group: 'Admin',
    items: [
      { label: 'Users & roles', to: '/admin', permission: 'admin' },
      { label: 'WhatsApp', to: '/whatsapp', permission: 'admin' },
      { label: 'Settings', to: '/settings', permission: 'settings' },
    ],
  },
]

export const SUB_PAGE_PERMISSIONS: Record<string, string> = {
  'vendor-detail': 'vendors',
  'worker-detail': 'hr',
  'repair-orders-management': 'repair-order',
}

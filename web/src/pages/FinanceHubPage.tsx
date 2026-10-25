import { Link } from 'react-router-dom'
import { PageHeader, Panel } from '../components/ui'

const links = [
  { to: '/finance/daily-expenses', label: 'Daily expenses' },
  { to: '/finance/major-expenses', label: 'Major expenses' },
  { to: '/finance/cash-received', label: 'Cash received' },
  { to: '/finance/monthly-ledger', label: 'Monthly ledger' },
  { to: '/invoices', label: 'Invoices' },
  { to: '/reports', label: 'Reports' },
]

export function FinanceHubPage() {
  return (
    <div>
      <PageHeader title="Finance management" />
      <Panel title="Modules">
        <div className="row-actions">
          {links.map((l) => (
            <Link key={l.to} className="btn btn-secondary" to={l.to}>
              {l.label}
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  )
}

import { useMemo, useState, type FormEvent } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { NAV } from './nav'

const ICONS: Record<string, string> = {
  '/': '▦',
  '/job-cards': '☰',
  '/cars': '▣',
  '/inventory': '▢',
  '/invoices': '≡',
  '/quotes/pending': '◎',
  '/repair-orders': '⚙',
  '/repair-execution': '🔧',
  '/finance': '₹',
  '/reports': '▤',
  '/vendors': '◇',
  '/settings': '⚙',
  '/admin': '★',
  '/whatsapp': '✆',
  '/labour-codes': 'L',
  '/hr/employees': '☺',
  '/money-in': '↓',
  '/money-out': '↑',
}

function titleFromPath(pathname: string): string {
  if (pathname === '/') return 'Dashboard'
  const hit = NAV.flatMap((g) => g.items).find(
    (i) => pathname === i.to || pathname.startsWith(i.to + '/'),
  )
  return hit?.label || pathname.split('/').filter(Boolean).pop()?.replaceAll('-', ' ') || 'GermanATO'
}

export function AppShell() {
  const { user, logout, canAccess } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [q, setQ] = useState('')

  const groups = NAV.map((g) => ({
    ...g,
    items: g.items.filter((i) => canAccess(i.permission)),
  })).filter((g) => g.items.length)

  const initial = (user?.username || '?').charAt(0).toUpperCase()
  const pageTitle = useMemo(() => titleFromPath(location.pathname), [location.pathname])

  function onSearch(e: FormEvent) {
    e.preventDefault()
    const term = q.trim()
    if (!term) return
    navigate(`/cars?q=${encodeURIComponent(term)}`)
  }

  return (
    <div className={`shell${collapsed ? ' is-collapsed' : ''}`}>
      <aside className="shell-nav" aria-label="Main">
        <NavLink to="/" className="shell-brand" end>
          <span className="shell-brand-mark">G</span>
          <span className="shell-brand-text">GermanATO</span>
        </NavLink>
        <nav className="shell-links">
          {groups.map((g) => (
            <div key={g.group || 'root'} className="shell-group">
              {g.group ? <p className="shell-group-label">{g.group}</p> : null}
              {g.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) => `shell-link${isActive ? ' is-active' : ''}`}
                  title={item.label}
                >
                  <span className="shell-link-ico" aria-hidden>
                    {ICONS[item.to] || '•'}
                  </span>
                  <span className="shell-link-label">{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="shell-footer">
          <div className="shell-user">
            <span className="shell-avatar">{initial}</span>
            <div className="shell-user-meta">
              <div className="shell-user-name">{user?.username}</div>
              <div className="shell-user-role">{(user?.role || '').replaceAll('_', ' ')}</div>
            </div>
          </div>
          <button
            type="button"
            className="shell-collapse"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? '»' : '«'}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={async () => {
              await logout()
              navigate('/login', { replace: true })
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="shell-body">
        <header className="shell-top">
          <div>
            <div className="shell-top-title">{pageTitle}</div>
            <div className="shell-top-sub">{(user?.role || '').replaceAll('_', ' ')}</div>
          </div>
          <div className="shell-top-actions">
            <form onSubmit={onSearch}>
              <input
                className="shell-search"
                placeholder="Search cars / plates…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                aria-label="Global search"
              />
            </form>
            <button type="button" className="shell-icon-btn" aria-label="Notifications" title="Notifications">
              🔔
              <span className="dot" />
            </button>
            <button
              type="button"
              className="shell-icon-btn"
              aria-label="Profile"
              title={user?.username}
              onClick={() => navigate('/settings')}
            >
              {initial}
            </button>
          </div>
        </header>
        <main className="shell-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { NAV } from './nav'

export function AppShell() {
  const { user, logout, canAccess } = useAuth()
  const navigate = useNavigate()

  const groups = NAV.map((g) => ({
    ...g,
    items: g.items.filter((i) => canAccess(i.permission)),
  })).filter((g) => g.items.length)

  const initial = (user?.username || '?').charAt(0).toUpperCase()

  return (
    <div className="shell">
      <aside className="shell-nav">
        <NavLink to="/" className="shell-brand" end>
          <span className="shell-brand-mark">G</span>
          <span>GermanATO</span>
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
                  className={({ isActive }) =>
                    `shell-link${isActive ? ' is-active' : ''}`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="shell-footer">
          <div className="shell-user">
            <span className="shell-avatar">{initial}</span>
            <div>
              <div className="shell-user-name">{user?.username}</div>
              <div className="shell-user-role">{(user?.role || '').replaceAll('_', ' ')}</div>
            </div>
          </div>
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
      <main className="shell-main">
        <Outlet />
      </main>
    </div>
  )
}

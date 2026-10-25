import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { configureApiClient, api } from '../api/client'
import { SUB_PAGE_PERMISSIONS } from '../layout/nav'
import type { AuthUser, LoginResponse } from '../types'

type AuthState = {
  user: AuthUser | null
  accessToken: string | null
  refreshToken: string | null
  permissions: string[] | null
  ready: boolean
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<{ ok: true } | { ok: false; error: string }>
  logout: () => Promise<void>
  canAccess: (permission: string) => boolean
  hasRole: (role: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

const ACCESS_KEY = 'accessToken'
const REFRESH_KEY = 'refreshToken'
const USER_KEY = 'user'
const PERMS_KEY = 'userPermissions'

function readUser(): AuthUser | null {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null') as AuthUser | null
  } catch {
    return null
  }
}

function readPerms(): string[] | null {
  try {
    const p = JSON.parse(localStorage.getItem(PERMS_KEY) || 'null') as unknown
    return Array.isArray(p) ? (p as string[]) : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => readUser())
  const [accessToken, setAccessTokenState] = useState<string | null>(
    () => localStorage.getItem(ACCESS_KEY),
  )
  const [refreshToken, setRefreshTokenState] = useState<string | null>(
    () => localStorage.getItem(REFRESH_KEY),
  )
  const [permissions, setPermissions] = useState<string[] | null>(() => readPerms())
  const [ready, setReady] = useState(false)

  const clearLocal = useCallback(() => {
    setUser(null)
    setAccessTokenState(null)
    setRefreshTokenState(null)
    setPermissions(null)
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(PERMS_KEY)
  }, [])

  const persistSession = useCallback(
    (access: string, refresh: string | null, nextUser: AuthUser) => {
      setAccessTokenState(access)
      localStorage.setItem(ACCESS_KEY, access)
      if (refresh) {
        setRefreshTokenState(refresh)
        localStorage.setItem(REFRESH_KEY, refresh)
      }
      setUser(nextUser)
      localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
    },
    [],
  )

  const loadPermissions = useCallback(async () => {
    try {
      const data = await api.get<{ permissions: string[] }>('/api/auth/permissions/my')
      setPermissions(data.permissions)
      localStorage.setItem(PERMS_KEY, JSON.stringify(data.permissions))
    } catch {
      /* server still guards each API call */
    }
  }, [])

  useEffect(() => {
    configureApiClient({
      getAccessToken: () => localStorage.getItem(ACCESS_KEY),
      getRefreshToken: () => localStorage.getItem(REFRESH_KEY),
      setAccessToken: (t) => {
        localStorage.setItem(ACCESS_KEY, t)
        setAccessTokenState(t)
      },
      clearAuth: clearLocal,
      onUnauthorized: () => {
        clearLocal()
        if (!window.location.pathname.startsWith('/login')) {
          window.location.assign('/login')
        }
      },
    })
  }, [clearLocal])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!localStorage.getItem(ACCESS_KEY)) {
        if (!cancelled) setReady(true)
        return
      }
      try {
        const data = await api.get<{ authenticated: boolean; user: AuthUser }>(
          '/api/auth/verify',
        )
        if (cancelled) return
        setUser(data.user)
        localStorage.setItem(USER_KEY, JSON.stringify(data.user))
        await loadPermissions()
      } catch {
        if (!cancelled) clearLocal()
      } finally {
        if (!cancelled) setReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [clearLocal, loadPermissions])

  const login = useCallback(
    async (username: string, password: string) => {
      try {
        const data = await api.post<LoginResponse>('/api/auth/login', {
          username,
          password,
        })
        persistSession(data.access_token, data.refresh_token, data.user)
        await loadPermissions()
        return { ok: true as const }
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Login failed'
        return { ok: false as const, error: msg }
      }
    },
    [loadPermissions, persistSession],
  )

  const logout = useCallback(async () => {
    try {
      if (localStorage.getItem(ACCESS_KEY)) {
        await api.post('/api/auth/logout')
      }
    } catch {
      /* still clear locally */
    } finally {
      clearLocal()
    }
  }, [clearLocal])

  const canAccess = useCallback(
    (permission: string) => {
      if (!user) return false
      if (user.role === 'admin' || permission === 'home') return true
      if (!permissions) return true
      const key = SUB_PAGE_PERMISSIONS[permission] || permission
      return permissions.includes(key)
    },
    [permissions, user],
  )

  const hasRole = useCallback(
    (role: string) => !!user && (user.role === 'admin' || user.role === role),
    [user],
  )

  const value = useMemo<AuthState>(
    () => ({
      user,
      accessToken,
      refreshToken,
      permissions,
      ready,
      isAuthenticated: !!accessToken,
      login,
      logout,
      canAccess,
      hasRole,
    }),
    [
      accessToken,
      canAccess,
      hasRole,
      login,
      logout,
      permissions,
      ready,
      refreshToken,
      user,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

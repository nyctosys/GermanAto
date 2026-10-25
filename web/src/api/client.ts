import type { ApiErrorBody } from '../types'

const ACCESS_KEY = 'accessToken'
const REFRESH_KEY = 'refreshToken'

type TokenGetter = () => string | null
type TokenSetter = (access: string) => void
type AuthClearer = () => void

let getAccessToken: TokenGetter = () => localStorage.getItem(ACCESS_KEY)
let getRefreshToken: TokenGetter = () => localStorage.getItem(REFRESH_KEY)
let setAccessToken: TokenSetter = (t) => localStorage.setItem(ACCESS_KEY, t)
let clearAuth: AuthClearer = () => {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem('user')
  localStorage.removeItem('userPermissions')
}
let onUnauthorized: () => void = () => {
  window.location.assign('/login')
}

export function configureApiClient(opts: {
  getAccessToken: TokenGetter
  getRefreshToken: TokenGetter
  setAccessToken: TokenSetter
  clearAuth: AuthClearer
  onUnauthorized: () => void
}) {
  getAccessToken = opts.getAccessToken
  getRefreshToken = opts.getRefreshToken
  setAccessToken = opts.setAccessToken
  clearAuth = opts.clearAuth
  onUnauthorized = opts.onUnauthorized
}

export class ApiError extends Error {
  status: number
  details?: string[] | string

  constructor(message: string, status: number, details?: string[] | string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function parseError(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => ({}))) as ApiErrorBody
  const message =
    body.error || body.message || `HTTP ${res.status}: ${res.statusText}`
  return new ApiError(message, res.status, body.details)
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  try {
    const res = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${refresh}`,
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) return false
    const data = (await res.json()) as { access_token: string; user?: unknown }
    setAccessToken(data.access_token)
    if (data.user) localStorage.setItem('user', JSON.stringify(data.user))
    return true
  } catch {
    return false
  }
}

export type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
  silent?: boolean
}

async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData
  if (!isForm && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const init: RequestInit = {
    ...options,
    headers,
    body:
      options.body === undefined
        ? undefined
        : isForm
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  }

  let res = await fetch(url, init)

  if (res.status === 401) {
    const ok = await refreshAccessToken()
    if (ok) {
      const retryHeaders = new Headers(headers)
      const next = getAccessToken()
      if (next) retryHeaders.set('Authorization', `Bearer ${next}`)
      res = await fetch(url, { ...init, headers: retryHeaders })
    } else {
      clearAuth()
      onUnauthorized()
      throw new ApiError('Session expired', 401)
    }
  }

  if (!res.ok) throw await parseError(res)

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(url: string) => request<T>(url, { method: 'GET' }),
  post: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: 'POST', body }),
  put: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: 'PUT', body }),
  patch: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: 'PATCH', body }),
  delete: <T>(url: string) => request<T>(url, { method: 'DELETE' }),
}

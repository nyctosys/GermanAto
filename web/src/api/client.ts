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
  /** Raw FastAPI detail object when present (e.g. assignment conflict). */
  detail?: unknown
  body?: ApiErrorBody

  constructor(
    message: string,
    status: number,
    details?: string[] | string,
    detail?: unknown,
    body?: ApiErrorBody,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
    this.detail = detail
    this.body = body
  }
}

async function parseError(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => ({}))) as ApiErrorBody & {
    detail?: unknown
  }
  const detail = body.detail
  const detailObj =
    detail && typeof detail === 'object' && !Array.isArray(detail)
      ? (detail as Record<string, unknown>)
      : null
  const message =
    (detailObj?.error as string | undefined) ||
    body.error ||
    body.message ||
    `HTTP ${res.status}: ${res.statusText}`
  return new ApiError(message, res.status, body.details, detail ?? body, body)
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
  reason?: string
  idempotencyKey?: string
  branchId?: string
}

const BRANCH_KEY = 'branchId'
const DEFAULT_BRANCH = 'a1b2c3d4'

function activeBranchId(override?: string): string {
  if (override && /^[0-9a-f]{8}$/.test(override)) return override
  const stored = localStorage.getItem(BRANCH_KEY)
  if (stored && /^[0-9a-f]{8}$/.test(stored)) return stored
  return DEFAULT_BRANCH
}

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `idemp-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export class VersionConflictError extends ApiError {
  currentVersion?: number

  constructor(message: string, currentVersion?: number) {
    super(message, 409)
    this.name = 'VersionConflictError'
    this.currentVersion = currentVersion
  }
}

async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const isForm = typeof FormData !== 'undefined' && options.body instanceof FormData
  if (!isForm && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  headers.set('X-Branch-Id', activeBranchId(options.branchId))
  if (options.reason) headers.set('X-Audit-Reason', options.reason)
  if (options.idempotencyKey) {
    headers.set('Idempotency-Key', options.idempotencyKey)
  }

  const { reason: _r, idempotencyKey: _i, branchId: _b, silent: _s, body, ...rest } =
    options

  const init: RequestInit = {
    ...rest,
    headers,
    body:
      body === undefined
        ? undefined
        : isForm
          ? (body as FormData)
          : JSON.stringify(body),
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

  if (res.status === 409) {
    const errBody = (await res.json().catch(() => ({}))) as {
      error?: string
      detail?: {
        error?: string
        current_version?: number
        override_kind?: string
        conflict?: unknown
        require_reason?: boolean
      }
      current_version?: number
      override_kind?: string
      conflict?: unknown
      require_reason?: boolean
    }
    // FastAPI handler flattens dict details onto the body for GermanATO.
    const flat = errBody.detail || errBody
    if (flat?.override_kind === 'assignment_conflict' || flat?.conflict) {
      throw new ApiError(
        (flat as { error?: string }).error || errBody.error || 'Assignment conflict',
        409,
        undefined,
        flat,
        errBody as ApiErrorBody,
      )
    }
    const message =
      errBody.error ||
      errBody.detail?.error ||
      'Version conflict — reload and try again'
    const current =
      errBody.current_version ?? errBody.detail?.current_version
    throw new VersionConflictError(message, current)
  }

  if (!res.ok) throw await parseError(res)

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(url: string, opts?: RequestOptions) =>
    request<T>(url, { ...opts, method: 'GET' }),
  post: <T>(url: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(url, {
      ...opts,
      method: 'POST',
      body,
      idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey(),
    }),
  put: <T>(url: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(url, {
      ...opts,
      method: 'PUT',
      body,
      reason: opts?.reason || 'Record updated',
      // Payments / create-like PUTs should pass or accept auto key
      idempotencyKey: opts?.idempotencyKey,
    }),
  /** PUT that always sends Idempotency-Key (invoice payments, etc.). */
  putIdempotent: <T>(url: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(url, {
      ...opts,
      method: 'PUT',
      body,
      reason: opts?.reason || 'Record updated',
      idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey(),
    }),
  patch: <T>(url: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(url, {
      ...opts,
      method: 'PATCH',
      body,
      reason: opts?.reason || 'Record updated',
    }),
  delete: <T>(url: string, opts?: RequestOptions) =>
    request<T>(url, {
      ...opts,
      method: 'DELETE',
      reason: opts?.reason || 'User deleted record',
    }),
}

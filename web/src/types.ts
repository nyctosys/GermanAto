export type AuthUser = {
  id: number
  username: string
  email: string
  role: string
}

export type LoginResponse = {
  message: string
  access_token: string
  refresh_token: string
  user: AuthUser
}

export type ApiErrorBody = {
  error?: string
  details?: string[] | string
  message?: string
  detail?: string | { error?: string; message?: string; detail?: string }
}

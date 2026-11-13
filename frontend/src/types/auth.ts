export const USER_ROLES = [
  'ADMIN',
  'OPERATIONS_MANAGER',
  'FLEET_MANAGER',
  'WAREHOUSE_MANAGER',
  'ANALYST',
] as const

export type UserRole = (typeof USER_ROLES)[number]

export interface UserRead {
  id: string
  username: string
  email: string
  full_name: string
  role: UserRole | string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  username?: string
  email?: string
  username_or_email?: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer' | string
  expires_in: number
  user: UserRead
}

export interface UserCreate {
  username: string
  email: string
  full_name: string
  password: string
  role: UserRole
}

export interface UserRoleUpdate {
  role: UserRole
}

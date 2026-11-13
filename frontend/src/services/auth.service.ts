import { apiClient } from '@/lib/api-client'
import type {
  LoginRequest,
  TokenResponse,
  UserCreate,
  UserRead,
  UserRole,
} from '@/types/auth'

export const authService = {
  async login(payload: LoginRequest): Promise<TokenResponse> {
    const { data } = await apiClient.post<TokenResponse>('/auth/login', payload)
    return data
  },

  async getMe(): Promise<UserRead> {
    const { data } = await apiClient.get<UserRead>('/auth/me')
    return data
  },

  async logout(): Promise<{ message: string; user_id: string }> {
    const { data } = await apiClient.post<{ message: string; user_id: string }>('/auth/logout')
    return data
  },

  async registerUser(payload: UserCreate): Promise<UserRead> {
    const { data } = await apiClient.post<UserRead>('/auth/register', payload)
    return data
  },

  async listAdminUsers(): Promise<UserRead[]> {
    const { data } = await apiClient.get<UserRead[]>('/admin/users')
    return data
  },

  async updateUserRole(userId: string, role: UserRole): Promise<UserRead> {
    const { data } = await apiClient.patch<UserRead>(`/admin/users/${userId}/role`, { role })
    return data
  },
}


import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { setUnauthorizedHandler } from '@/lib/api-client'
import { queryClient } from '@/lib/query-client'
import { tokenStorage } from '@/lib/token-storage'
import { authService } from '@/services/auth.service'
import type { LoginRequest, UserRead } from '@/types/auth'

interface AuthContextValue {
  user: UserRead | null
  token: string | null
  isAuthenticated: boolean
  isInitializing: boolean
  login: (payload: LoginRequest, remember?: boolean) => Promise<UserRead>
  logout: () => Promise<void>
  refreshMe: () => Promise<UserRead | null>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredUser(): UserRead | null {
  const raw = tokenStorage.getUserJson()
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserRead
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => tokenStorage.getToken())
  const [user, setUser] = useState<UserRead | null>(() => readStoredUser())
  const [isInitializing, setIsInitializing] = useState<boolean>(() => Boolean(tokenStorage.getToken()))

  const clearSession = useCallback(() => {
    tokenStorage.clear()
    setToken(null)
    setUser(null)
    queryClient.clear()
  }, [])

  const refreshMe = useCallback(async (): Promise<UserRead | null> => {
    const currentToken = tokenStorage.getToken()
    if (!currentToken) {
      clearSession()
      return null
    }
    const persist = Boolean(window.localStorage.getItem('logipulse_access_token'))
    try {
      const freshUser = await authService.getMe()
      tokenStorage.setUserJson(JSON.stringify(freshUser), persist)
      setUser(freshUser)
      return freshUser
    } catch {
      clearSession()
      return null
    }
  }, [clearSession])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession()
    })
    return () => setUnauthorizedHandler(null)
  }, [clearSession])

  useEffect(() => {
    let active = true
    async function bootstrap() {
      const storedToken = tokenStorage.getToken()
      if (!storedToken) {
        if (active) setIsInitializing(false)
        return
      }
      await refreshMe()
      if (active) setIsInitializing(false)
    }
    void bootstrap()
    return () => {
      active = false
    }
  }, [refreshMe])

  const login = useCallback(async (payload: LoginRequest, remember = true): Promise<UserRead> => {
    const res = await authService.login(payload)
    tokenStorage.setToken(res.access_token, remember)
    tokenStorage.setUserJson(JSON.stringify(res.user), remember)
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const logout = useCallback(async (): Promise<void> => {
    try {
      if (tokenStorage.getToken()) {
        await authService.logout()
      }
    } catch {
      // Stateless logout: clear client token even if server session already expired
    } finally {
      clearSession()
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token && user),
      isInitializing,
      login,
      logout,
      refreshMe,
    }),
    [user, token, isInitializing, login, logout, refreshMe],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>')
  }
  return ctx
}

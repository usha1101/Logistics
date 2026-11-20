const ACCESS_TOKEN_KEY = 'logipulse_access_token'
const USER_JSON_KEY = 'logipulse_user'

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key) ?? window.sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string, remember: boolean): void {
  try {
    if (remember) {
      window.localStorage.setItem(key, value)
      window.sessionStorage.removeItem(key)
    } else {
      window.sessionStorage.setItem(key, value)
      window.localStorage.removeItem(key)
    }
  } catch {
    // Ignore storage write errors in restricted browsing modes
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key)
    window.sessionStorage.removeItem(key)
  } catch {
    // Ignore storage remove errors
  }
}

export const tokenStorage = {
  getToken(): string | null {
    return safeGet(ACCESS_TOKEN_KEY)
  },

  setToken(token: string, remember = true): void {
    safeSet(ACCESS_TOKEN_KEY, token, remember)
  },

  getUserJson(): string | null {
    return safeGet(USER_JSON_KEY)
  },

  setUserJson(json: string, remember = true): void {
    safeSet(USER_JSON_KEY, json, remember)
  },

  clear(): void {
    safeRemove(ACCESS_TOKEN_KEY)
    safeRemove(USER_JSON_KEY)
  },
}


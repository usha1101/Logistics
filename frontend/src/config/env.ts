const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1'

function normalizeBaseUrl(rawUrl: string | undefined): string {
  const trimmed = rawUrl?.trim()
  const base = trimmed && trimmed.length > 0 ? trimmed : DEFAULT_API_BASE_URL
  return base.replace(/\/+$/, '')
}

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)
const WS_BASE_URL = API_BASE_URL.replace(/^http/i, 'ws')

export const env = {
  API_BASE_URL,
  WS_BASE_URL,
} as const


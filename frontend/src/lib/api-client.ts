import axios, { AxiosHeaders, type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { env } from '@/config/env'
import { tokenStorage } from '@/lib/token-storage'

type UnauthorizedHandler = () => void

let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

export const apiClient = axios.create({
  baseURL: env.API_BASE_URL,
  timeout: 30_000,
  headers: {
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStorage.getToken()
  if (token) {
    const headers = AxiosHeaders.from(config.headers)
    headers.set('Authorization', `Bearer ${token}`)
    config.headers = headers
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status
    const requestUrl = error.config?.url ?? ''
    const isLoginRequest = requestUrl.includes('/auth/login')

    if (status === 401 && !isLoginRequest && unauthorizedHandler) {
      unauthorizedHandler()
    }

    return Promise.reject(error)
  },
)

export async function downloadProtectedFile(url: string, filename: string): Promise<void> {
  const response = await apiClient.get<Blob>(url, {
    responseType: 'blob',
  })

  const blob = response.data instanceof Blob ? response.data : new Blob([response.data])
  const objectUrl = window.URL.createObjectURL(blob)

  try {
    const anchor = document.createElement('a')
    anchor.href = objectUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
  } finally {
    window.URL.revokeObjectURL(objectUrl)
  }
}


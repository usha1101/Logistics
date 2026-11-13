export interface BackendErrorDetail {
  code: string
  message: string
  details?: unknown
}

export interface BackendErrorEnvelope {
  error: BackendErrorDetail
  request_id: string
}

export interface OffsetPaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export interface PagePaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DatabaseHealth {
  connected: boolean
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  app: string
  version: string
  environment: string
  database: DatabaseHealth
  server_time_utc: string
  data_source: 'SIMULATED'
}


import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/lib/api-client'
import type { HealthResponse } from '@/types/common'

async function fetchHealthStatus(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health')
  return data
}

export function useHealthCheck(enabled = false) {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: fetchHealthStatus,
    enabled,
    retry: false,
  })
}


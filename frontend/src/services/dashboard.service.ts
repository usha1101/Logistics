import { apiClient } from '@/lib/api-client'
import type { DashboardSummaryResponse } from '@/types/dashboard'

export const dashboardService = {
  async getSummary(): Promise<DashboardSummaryResponse> {
    const { data } = await apiClient.get<DashboardSummaryResponse>('/dashboard/summary')
    return data
  },
}


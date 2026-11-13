import { apiClient } from '@/lib/api-client'
import type {
  AgentExecutionRead,
  AgentRecommendationRead,
  AgentRunRead,
  AgentRunStatus,
  ProviderStatusResponse,
} from '@/types/agent'
import type { PagePaginatedResponse } from '@/types/common'

export const agentService = {
  async getProviderStatus(): Promise<ProviderStatusResponse> {
    const { data } = await apiClient.get<ProviderStatusResponse>('/agents/status')
    return data
  },

  async listRuns(params?: {
    disruption_id?: string
    status?: AgentRunStatus | string
    page?: number
    page_size?: number
  }): Promise<PagePaginatedResponse<AgentRunRead>> {
    const { data } = await apiClient.get<PagePaginatedResponse<AgentRunRead>>('/agents/runs', {
      params,
    })
    return data
  },

  async getRun(runId: string): Promise<AgentRunRead> {
    const { data } = await apiClient.get<AgentRunRead>(`/agents/runs/${runId}`)
    return data
  },

  async analyzeDisruption(disruptionId: string): Promise<AgentRunRead> {
    const { data } = await apiClient.post<AgentRunRead>(`/agents/analyze/${disruptionId}`)
    return data
  },

  async retryRun(runId: string): Promise<AgentRunRead> {
    const { data } = await apiClient.post<AgentRunRead>(`/agents/runs/${runId}/retry`)
    return data
  },

  async getExecutions(runId: string): Promise<AgentExecutionRead[]> {
    const { data } = await apiClient.get<AgentExecutionRead[]>(`/agents/runs/${runId}/executions`)
    return data
  },

  async getRecommendations(runId: string): Promise<AgentRecommendationRead[]> {
    const { data } = await apiClient.get<AgentRecommendationRead[]>(
      `/agents/runs/${runId}/recommendations`,
    )
    return data
  },
}


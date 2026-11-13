import { apiClient } from '@/lib/api-client'
import type { PagePaginatedResponse } from '@/types/common'
import type {
  DisruptionAnalysisReport,
  DisruptionCancelRequest,
  DisruptionCreate,
  DisruptionEventRead,
  DisruptionRead,
  DisruptionResolveRequest,
  DisruptionSeverity,
  DisruptionStatus,
  DisruptionSummary,
  DisruptionType,
} from '@/types/disruption'

export const disruptionService = {
  async listDisruptions(params?: {
    status?: DisruptionStatus | string
    disruption_type?: DisruptionType | string
    severity?: DisruptionSeverity | string
    simulation_id?: string
    page?: number
    page_size?: number
  }): Promise<PagePaginatedResponse<DisruptionSummary>> {
    const { data } = await apiClient.get<PagePaginatedResponse<DisruptionSummary>>(
      '/disruptions',
      { params },
    )
    return data
  },

  async listActiveDisruptions(params?: {
    simulation_id?: string
    page?: number
    page_size?: number
  }): Promise<PagePaginatedResponse<DisruptionSummary>> {
    const { data } = await apiClient.get<PagePaginatedResponse<DisruptionSummary>>(
      '/disruptions/active',
      { params },
    )
    return data
  },

  async getDisruption(disruptionId: string): Promise<DisruptionRead> {
    const { data } = await apiClient.get<DisruptionRead>(`/disruptions/${disruptionId}`)
    return data
  },

  async createDisruption(payload: DisruptionCreate): Promise<DisruptionRead> {
    const { data } = await apiClient.post<DisruptionRead>('/disruptions', payload)
    return data
  },

  async activateDisruption(disruptionId: string): Promise<DisruptionRead> {
    const { data } = await apiClient.post<DisruptionRead>(`/disruptions/${disruptionId}/activate`)
    return data
  },

  async monitorDisruption(disruptionId: string): Promise<DisruptionRead> {
    const { data } = await apiClient.post<DisruptionRead>(`/disruptions/${disruptionId}/monitor`)
    return data
  },

  async resolveDisruption(
    disruptionId: string,
    payload?: DisruptionResolveRequest,
  ): Promise<DisruptionRead> {
    const { data } = await apiClient.post<DisruptionRead>(
      `/disruptions/${disruptionId}/resolve`,
      payload ?? {},
    )
    return data
  },

  async cancelDisruption(
    disruptionId: string,
    payload?: DisruptionCancelRequest,
  ): Promise<DisruptionRead> {
    const { data } = await apiClient.post<DisruptionRead>(
      `/disruptions/${disruptionId}/cancel`,
      payload ?? {},
    )
    return data
  },

  async getImpactAnalysis(disruptionId: string): Promise<DisruptionAnalysisReport> {
    const { data } = await apiClient.get<DisruptionAnalysisReport>(
      `/disruptions/${disruptionId}/impact`,
    )
    return data
  },

  async getEvents(
    disruptionId: string,
    params?: { page?: number; page_size?: number },
  ): Promise<PagePaginatedResponse<DisruptionEventRead>> {
    const { data } = await apiClient.get<PagePaginatedResponse<DisruptionEventRead>>(
      `/disruptions/${disruptionId}/events`,
      { params },
    )
    return data
  },
}


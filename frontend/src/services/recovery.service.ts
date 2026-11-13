import { apiClient } from '@/lib/api-client'
import type { PagePaginatedResponse } from '@/types/common'
import type {
  RecoveryActionRead,
  RecoveryAuditLogRead,
  RecoveryComparisonRead,
  RecoveryKPISummary,
  RecoveryPlanApproveRequest,
  RecoveryPlanGenerateRequest,
  RecoveryPlanRead,
  RecoveryPlanRejectRequest,
  RecoveryPlanStatus,
  RecoveryPlanValidationReport,
} from '@/types/recovery'

export const recoveryService = {
  async getSummary(): Promise<RecoveryKPISummary> {
    const { data } = await apiClient.get<RecoveryKPISummary>('/recovery/summary')
    return data
  },

  async listPlans(params?: {
    disruption_id?: string
    status?: RecoveryPlanStatus | string
    page?: number
    page_size?: number
  }): Promise<PagePaginatedResponse<RecoveryPlanRead>> {
    const { data } = await apiClient.get<PagePaginatedResponse<RecoveryPlanRead>>(
      '/recovery/plans',
      { params },
    )
    return data
  },

  async getPlan(planId: string): Promise<RecoveryPlanRead> {
    const { data } = await apiClient.get<RecoveryPlanRead>(`/recovery/plans/${planId}`)
    return data
  },

  async generatePlan(payload: RecoveryPlanGenerateRequest): Promise<RecoveryPlanRead> {
    const { data } = await apiClient.post<RecoveryPlanRead>('/recovery/plans/generate', payload)
    return data
  },

  async validatePlan(planId: string): Promise<RecoveryPlanValidationReport> {
    const { data } = await apiClient.post<RecoveryPlanValidationReport>(
      `/recovery/plans/${planId}/validate`,
    )
    return data
  },

  async approvePlan(planId: string, payload?: RecoveryPlanApproveRequest): Promise<RecoveryPlanRead> {
    const { data } = await apiClient.post<RecoveryPlanRead>(
      `/recovery/plans/${planId}/approve`,
      payload ?? {},
    )
    return data
  },

  async rejectPlan(planId: string, payload: RecoveryPlanRejectRequest): Promise<RecoveryPlanRead> {
    const { data } = await apiClient.post<RecoveryPlanRead>(
      `/recovery/plans/${planId}/reject`,
      payload,
    )
    return data
  },

  async executePlan(planId: string): Promise<RecoveryPlanRead> {
    const { data } = await apiClient.post<RecoveryPlanRead>(`/recovery/plans/${planId}/execute`)
    return data
  },

  async getComparisons(planId: string): Promise<RecoveryComparisonRead[]> {
    const { data } = await apiClient.get<RecoveryComparisonRead[]>(
      `/recovery/plans/${planId}/comparison`,
    )
    return data
  },

  async getActions(planId: string): Promise<RecoveryActionRead[]> {
    const { data } = await apiClient.get<RecoveryActionRead[]>(
      `/recovery/plans/${planId}/actions`,
    )
    return data
  },

  async getAuditLogs(planId: string): Promise<RecoveryAuditLogRead[]> {
    const { data } = await apiClient.get<RecoveryAuditLogRead[]>(
      `/recovery/plans/${planId}/audit-logs`,
    )
    return data
  },
}


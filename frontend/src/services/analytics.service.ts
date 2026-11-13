import { apiClient, downloadProtectedFile } from '@/lib/api-client'
import type {
  AgentAnalyticsResponse,
  AnalyticsHealthResponse,
  DisruptionAnalyticsResponse,
  FleetAnalyticsResponse,
  OrderAnalyticsResponse,
  OverviewAnalyticsResponse,
  PerformanceComparisonResponse,
  RecoveryAnalyticsResponse,
  ReportGenerateRequest,
  ReportMetadataRead,
  ReportStatus,
  ReportType,
  ReportTypesListResponse,
  TrendGrouping,
  TrendSeriesResponse,
} from '@/types/analytics'
import type { HealthResponse, OffsetPaginatedResponse } from '@/types/common'

export interface AnalyticsQueryParams {
  start_date?: string
  end_date?: string
  simulation_id?: string
  include_simulations?: boolean
}

export const analyticsService = {
  async getSystemHealth(): Promise<HealthResponse> {
    const { data } = await apiClient.get<HealthResponse>('/health')
    return data
  },

  async getAnalyticsHealth(): Promise<AnalyticsHealthResponse> {
    const { data } = await apiClient.get<AnalyticsHealthResponse>('/analytics/health')
    return data
  },

  async getOverview(params?: AnalyticsQueryParams): Promise<OverviewAnalyticsResponse> {
    const { data } = await apiClient.get<OverviewAnalyticsResponse>('/analytics/overview', {
      params,
    })
    return data
  },

  async getOrders(params?: AnalyticsQueryParams): Promise<OrderAnalyticsResponse> {
    const { data } = await apiClient.get<OrderAnalyticsResponse>('/analytics/orders', { params })
    return data
  },

  async getOrderTrends(
    params?: AnalyticsQueryParams & { grouping?: TrendGrouping },
  ): Promise<TrendSeriesResponse> {
    const { data } = await apiClient.get<TrendSeriesResponse>('/analytics/orders/trends', {
      params,
    })
    return data
  },

  async getFleet(params?: AnalyticsQueryParams): Promise<FleetAnalyticsResponse> {
    const { data } = await apiClient.get<FleetAnalyticsResponse>('/analytics/fleet', { params })
    return data
  },

  async getDisruptions(params?: AnalyticsQueryParams): Promise<DisruptionAnalyticsResponse> {
    const { data } = await apiClient.get<DisruptionAnalyticsResponse>('/analytics/disruptions', {
      params,
    })
    return data
  },

  async getDisruptionTrends(
    params?: AnalyticsQueryParams & { grouping?: TrendGrouping },
  ): Promise<TrendSeriesResponse> {
    const { data } = await apiClient.get<TrendSeriesResponse>('/analytics/disruptions/trends', {
      params,
    })
    return data
  },

  async getAgents(params?: AnalyticsQueryParams): Promise<AgentAnalyticsResponse> {
    const { data } = await apiClient.get<AgentAnalyticsResponse>('/analytics/agents', { params })
    return data
  },

  async getRecovery(params?: AnalyticsQueryParams): Promise<RecoveryAnalyticsResponse> {
    const { data } = await apiClient.get<RecoveryAnalyticsResponse>('/analytics/recovery', {
      params,
    })
    return data
  },

  async getComparisons(
    params?: AnalyticsQueryParams & { disruption_id?: string; recovery_plan_id?: string },
  ): Promise<PerformanceComparisonResponse> {
    const { data } = await apiClient.get<PerformanceComparisonResponse>(
      '/analytics/comparisons',
      { params },
    )
    return data
  },

  async listReports(params?: {
    skip?: number
    limit?: number
    report_type?: ReportType | string
    status?: ReportStatus | string
  }): Promise<OffsetPaginatedResponse<ReportMetadataRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<ReportMetadataRead>>('/reports', {
      params,
    })
    return data
  },

  async getReportTypes(): Promise<ReportTypesListResponse> {
    const { data } = await apiClient.get<ReportTypesListResponse>('/reports/types')
    return data
  },

  async generateReport(payload: ReportGenerateRequest): Promise<ReportMetadataRead> {
    const { data } = await apiClient.post<ReportMetadataRead>('/reports/generate', payload)
    return data
  },

  async downloadReport(reportId: string, filename: string): Promise<void> {
    await downloadProtectedFile(`/reports/${reportId}/download`, filename)
  },
}


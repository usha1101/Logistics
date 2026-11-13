import { env } from '@/config/env'
import { apiClient } from '@/lib/api-client'
import type { OffsetPaginatedResponse } from '@/types/common'
import type {
  SimulationCreate,
  SimulationEventRead,
  SimulationRead,
  SimulationStatus,
  SimulationSummary,
  SimulationTelemetryRead,
  SimulationVehicleCreate,
  SimulationVehicleRead,
} from '@/types/simulation'

export const simulationService = {
  async listSimulations(params?: {
    status?: SimulationStatus | string
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<SimulationRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<SimulationRead>>('/simulations', {
      params,
    })
    return data
  },

  async createSimulation(payload?: SimulationCreate): Promise<SimulationRead> {
    const { data } = await apiClient.post<SimulationRead>('/simulations', payload ?? {})
    return data
  },

  async getSimulation(simulationId: string): Promise<SimulationRead> {
    const { data } = await apiClient.get<SimulationRead>(`/simulations/${simulationId}`)
    return data
  },

  async getSummary(simulationId: string): Promise<SimulationSummary> {
    const { data } = await apiClient.get<SimulationSummary>(`/simulations/${simulationId}/summary`)
    return data
  },

  async start(simulationId: string): Promise<SimulationRead> {
    const { data } = await apiClient.post<SimulationRead>(`/simulations/${simulationId}/start`)
    return data
  },

  async pause(simulationId: string): Promise<SimulationRead> {
    const { data } = await apiClient.post<SimulationRead>(`/simulations/${simulationId}/pause`)
    return data
  },

  async resume(simulationId: string): Promise<SimulationRead> {
    const { data } = await apiClient.post<SimulationRead>(`/simulations/${simulationId}/resume`)
    return data
  },

  async stop(simulationId: string): Promise<SimulationRead> {
    const { data } = await apiClient.post<SimulationRead>(`/simulations/${simulationId}/stop`)
    return data
  },

  async reset(simulationId: string): Promise<SimulationRead> {
    const { data } = await apiClient.post<SimulationRead>(`/simulations/${simulationId}/reset`)
    return data
  },

  async updateSpeed(simulationId: string, speedMultiplier: number): Promise<SimulationRead> {
    const { data } = await apiClient.patch<SimulationRead>(`/simulations/${simulationId}/speed`, {
      speed_multiplier: speedMultiplier,
    })
    return data
  },

  async assignVehicle(
    simulationId: string,
    payload: SimulationVehicleCreate,
  ): Promise<SimulationVehicleRead> {
    const { data } = await apiClient.post<SimulationVehicleRead>(
      `/simulations/${simulationId}/vehicles`,
      payload,
    )
    return data
  },

  async listVehicles(simulationId: string): Promise<SimulationVehicleRead[]> {
    const { data } = await apiClient.get<SimulationVehicleRead[]>(
      `/simulations/${simulationId}/vehicles`,
    )
    return data
  },

  async listEvents(
    simulationId: string,
    params?: { skip?: number; limit?: number },
  ): Promise<OffsetPaginatedResponse<SimulationEventRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<SimulationEventRead>>(
      `/simulations/${simulationId}/events`,
      { params },
    )
    return data
  },

  async listTelemetry(
    simulationId: string,
    params?: { vehicle_id?: string; skip?: number; limit?: number },
  ): Promise<OffsetPaginatedResponse<SimulationTelemetryRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<SimulationTelemetryRead>>(
      `/simulations/${simulationId}/telemetry`,
      { params },
    )
    return data
  },

  getWebSocketUrl(simulationId: string): string {
    return `${env.WS_BASE_URL}/simulations/${simulationId}/ws`
  },
}


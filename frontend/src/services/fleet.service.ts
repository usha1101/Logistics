import { apiClient } from '@/lib/api-client'
import type { OffsetPaginatedResponse } from '@/types/common'
import type {
  FleetSummaryResponse,
  VehicleCreate,
  VehicleLocationRead,
  VehicleLocationUpdate,
  VehicleRead,
  VehicleStatus,
  VehicleStatusChangeResponse,
  VehicleStatusUpdate,
  VehicleType,
} from '@/types/fleet'

export const fleetService = {
  async getSummary(): Promise<FleetSummaryResponse> {
    const { data } = await apiClient.get<FleetSummaryResponse>('/fleet/summary')
    return data
  },

  async listVehicles(params?: {
    status?: VehicleStatus | string
    vehicle_type?: VehicleType | string
    home_warehouse_id?: string
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<VehicleRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<VehicleRead>>('/fleet/vehicles', {
      params,
    })
    return data
  },

  async listAvailableVehicles(params?: {
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<VehicleRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<VehicleRead>>(
      '/fleet/vehicles/available',
      { params },
    )
    return data
  },

  async getVehicle(vehicleId: string): Promise<VehicleRead> {
    const { data } = await apiClient.get<VehicleRead>(`/fleet/vehicles/${vehicleId}`)
    return data
  },

  async createVehicle(payload: VehicleCreate): Promise<VehicleRead> {
    const { data } = await apiClient.post<VehicleRead>('/fleet/vehicles', payload)
    return data
  },

  async updateVehicleStatus(
    vehicleId: string,
    payload: VehicleStatusUpdate,
  ): Promise<VehicleStatusChangeResponse> {
    const { data } = await apiClient.patch<VehicleStatusChangeResponse>(
      `/fleet/vehicles/${vehicleId}/status`,
      payload,
    )
    return data
  },

  async updateVehicleLocation(
    vehicleId: string,
    payload: VehicleLocationUpdate,
  ): Promise<VehicleLocationRead> {
    const { data } = await apiClient.patch<VehicleLocationRead>(
      `/fleet/vehicles/${vehicleId}/location`,
      payload,
    )
    return data
  },

  async getLocationHistory(
    vehicleId: string,
    params?: { skip?: number; limit?: number },
  ): Promise<OffsetPaginatedResponse<VehicleLocationRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<VehicleLocationRead>>(
      `/fleet/vehicles/${vehicleId}/history`,
      { params },
    )
    return data
  },
}


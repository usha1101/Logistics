import { apiClient } from '@/lib/api-client'
import type { OffsetPaginatedResponse } from '@/types/common'
import type {
  InventoryItemCreate,
  InventoryItemRead,
  StockMovementCreate,
  StockMovementRead,
  WarehouseRead,
  WarehouseStatus,
  WarehouseSummaryResponse,
  WarehouseType,
  WarehouseUpdate,
} from '@/types/warehouse'

export const warehouseService = {
  async getSummary(): Promise<WarehouseSummaryResponse> {
    const { data } = await apiClient.get<WarehouseSummaryResponse>('/warehouses/summary')
    return data
  },

  async listWarehouses(params?: {
    status?: WarehouseStatus | string
    warehouse_type?: WarehouseType | string
    region?: string
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<WarehouseRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<WarehouseRead>>('/warehouses', {
      params,
    })
    return data
  },

  async getWarehouse(warehouseId: string): Promise<WarehouseRead> {
    const { data } = await apiClient.get<WarehouseRead>(`/warehouses/${warehouseId}`)
    return data
  },

  async updateWarehouse(warehouseId: string, payload: WarehouseUpdate): Promise<WarehouseRead> {
    const { data } = await apiClient.patch<WarehouseRead>(`/warehouses/${warehouseId}`, payload)
    return data
  },

  async listInventory(
    warehouseId: string,
    params?: { category?: string; skip?: number; limit?: number },
  ): Promise<OffsetPaginatedResponse<InventoryItemRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<InventoryItemRead>>(
      `/warehouses/${warehouseId}/inventory`,
      { params },
    )
    return data
  },

  async createInventoryItem(
    warehouseId: string,
    payload: InventoryItemCreate,
  ): Promise<InventoryItemRead> {
    const { data } = await apiClient.post<InventoryItemRead>(
      `/warehouses/${warehouseId}/inventory`,
      payload,
    )
    return data
  },

  async listLowStock(params?: {
    warehouse_id?: string
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<InventoryItemRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<InventoryItemRead>>(
      '/inventory/low-stock',
      { params },
    )
    return data
  },

  async recordMovement(
    inventoryItemId: string,
    payload: StockMovementCreate,
  ): Promise<StockMovementRead> {
    const { data } = await apiClient.post<StockMovementRead>(
      `/inventory/${inventoryItemId}/movements`,
      payload,
    )
    return data
  },

  async listMovements(
    inventoryItemId: string,
    params?: { skip?: number; limit?: number },
  ): Promise<OffsetPaginatedResponse<StockMovementRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<StockMovementRead>>(
      `/inventory/${inventoryItemId}/movements`,
      { params },
    )
    return data
  },
}


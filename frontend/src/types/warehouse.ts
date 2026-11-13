import type { NetworkNodeRead } from './network'

export type WarehouseStatus = 'OPERATIONAL' | 'DEGRADED' | 'CLOSED' | 'MAINTENANCE'
export type WarehouseType = 'DISTRIBUTION_CENTER' | 'FULFILLMENT_CENTER' | 'STORAGE_FACILITY'
export type MovementType = 'STOCK_RECEIVED' | 'STOCK_DISPATCHED' | 'STOCK_ADJUSTMENT'
export type StockStatus = 'OUT_OF_STOCK' | 'LOW_STOCK' | 'IN_STOCK'

export interface WarehouseRead {
  id: string
  network_node_id: string
  warehouse_code: string
  warehouse_type: WarehouseType | string
  total_capacity: number
  used_capacity: number
  available_capacity: number
  utilization_percentage: number
  status: WarehouseStatus | string
  manager_name: string | null
  contact_number: string | null
  operating_hours: Record<string, string> | null
  network_node: NetworkNodeRead | null
  created_at: string | null
  updated_at: string | null
}

export interface WarehouseUpdate {
  warehouse_type?: WarehouseType
  total_capacity?: number
  status?: WarehouseStatus
  manager_name?: string
  contact_number?: string
  operating_hours?: Record<string, string>
}

export interface InventoryItemRead {
  id: string
  warehouse_id: string
  sku: string
  product_name: string
  category: string | null
  quantity: number
  reorder_level: number
  unit: string
  unit_volume: number | null
  status: StockStatus
  created_at: string | null
  updated_at: string | null
}

export interface InventoryItemCreate {
  sku: string
  product_name: string
  category?: string
  quantity: number
  reorder_level: number
  unit?: string
  unit_volume?: number
}

export interface StockMovementCreate {
  movement_type: MovementType
  quantity: number
  adjustment_type?: 'INCREASE' | 'DECREASE'
  reference?: string
  notes?: string
}

export interface StockMovementRead {
  id: string
  inventory_item_id: string
  movement_type: MovementType | string
  quantity: number
  previous_quantity: number
  new_quantity: number
  reference: string | null
  notes: string | null
  created_by_user_id: string | null
  created_at: string
}

export interface WarehouseSummaryResponse {
  total_warehouses: number
  operational_warehouses: number
  degraded_warehouses: number
  closed_warehouses: number
  total_storage_capacity: number
  used_storage_capacity: number
  available_storage_capacity: number
  average_utilization_percentage: number | null
  total_inventory_records: number
  low_stock_items: number
  out_of_stock_items: number
  generated_at: string
  data_source: string
}


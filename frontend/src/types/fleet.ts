export type VehicleType = 'HEAVY_TRUCK' | 'MEDIUM_TRUCK' | 'DELIVERY_VAN' | 'ELECTRIC_VAN'

export type VehicleStatus =
  | 'AVAILABLE'
  | 'IDLE'
  | 'IN_TRANSIT'
  | 'BREAKDOWN'
  | 'MAINTENANCE'
  | 'OFFLINE'

export type LocationSource = 'SIMULATION' | 'MANUAL' | 'GPS'

export interface WarehouseMiniRead {
  id: string
  warehouse_code: string
  warehouse_type: string
  status: string
}

export interface VehicleRead {
  id: string
  vehicle_code: string
  registration_number: string
  vehicle_type: VehicleType | string
  manufacturer: string | null
  model: string | null
  capacity_kg: number
  current_load_kg: number
  remaining_capacity_kg: number
  status: VehicleStatus | string
  home_warehouse_id: string | null
  current_latitude: number | null
  current_longitude: number | null
  current_speed_kmph: number | null
  heading_degrees: number | null
  coordinates: [number, number] | null
  is_active: boolean
  last_location_update: string | null
  created_at: string
  updated_at: string
  home_warehouse: WarehouseMiniRead | null
}

export interface VehicleCreate {
  vehicle_code: string
  registration_number: string
  vehicle_type: VehicleType
  manufacturer?: string
  model?: string
  capacity_kg: number
  home_warehouse_id?: string | null
  is_active?: boolean
  initial_latitude?: number | null
  initial_longitude?: number | null
  initial_speed_kmph?: number | null
  initial_heading_degrees?: number | null
}

export interface VehicleStatusUpdate {
  status: VehicleStatus
  reason?: string
}

export interface VehicleLocationUpdate {
  latitude: number
  longitude: number
  speed_kmph?: number
  heading_degrees?: number
  source?: LocationSource
}

export interface VehicleLocationRead {
  id: string
  vehicle_id: string
  latitude: number
  longitude: number
  speed_kmph: number | null
  heading_degrees: number | null
  coordinates: [number, number]
  recorded_at: string
  source: LocationSource | string
}

export interface VehicleStatusHistoryRead {
  id: string
  vehicle_id: string
  previous_status: string | null
  new_status: string
  reason: string | null
  changed_by_user_id: string | null
  changed_at: string
}

export interface VehicleStatusChangeResponse {
  vehicle: VehicleRead
  status_history: VehicleStatusHistoryRead | null
}

export interface FleetSummaryResponse {
  total_vehicles: number
  active_vehicles: number
  available_vehicles: number
  idle_vehicles: number
  in_transit_vehicles: number
  breakdown_vehicles: number
  maintenance_vehicles: number
  offline_vehicles: number
  total_capacity_kg: number
  current_load_kg: number
  available_capacity_kg: number
  fleet_utilization_percentage: number | null
  generated_at: string
  data_source: string
}


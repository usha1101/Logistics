export type SimulationStatus = 'CREATED' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'STOPPED' | 'FAILED'

export type SimulationVehicleStatus = 'QUEUED' | 'EN_ROUTE' | 'PAUSED' | 'BREAKDOWN' | 'ARRIVED'

export type SimulationEventType =
  | 'SIMULATION_STARTED'
  | 'SIMULATION_PAUSED'
  | 'SIMULATION_RESUMED'
  | 'SIMULATION_STOPPED'
  | 'SIMULATION_RESET'
  | 'SIMULATION_SPEED_CHANGED'
  | 'VEHICLE_ASSIGNED'
  | 'VEHICLE_DEPARTED'
  | 'VEHICLE_POSITION_UPDATED'
  | 'VEHICLE_ARRIVED'
  | 'SIMULATION_COMPLETED'
  | 'SIMULATION_FAILED'

export interface SimulationCreate {
  name?: string
  seed?: number
  simulation_speed_multiplier?: number
  configuration?: Record<string, unknown>
}

export interface SimulationSpeedUpdate {
  speed_multiplier: number
}

export interface SimulationVehicleCreate {
  vehicle_id: string
  origin_node_id: string
  destination_node_id: string
}

export interface SimulationVehicleRead {
  id: string
  simulation_id: string
  vehicle_id: string
  vehicle_code: string | null
  origin_node_id: string
  destination_node_id: string
  origin_node_name: string | null
  destination_node_name: string | null
  route_node_ids: string[]
  current_route_segment: number
  segment_progress: number
  progress_percentage: number
  current_latitude: number
  current_longitude: number
  current_speed_kmph: number
  heading_degrees: number
  status: SimulationVehicleStatus | string
  coordinates: [number, number]
  simulated_departure_time: string | null
  estimated_arrival_time: string | null
  actual_arrival_time: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SimulationEventRead {
  id: string
  simulation_id: string
  vehicle_id: string | null
  event_type: SimulationEventType | string
  event_data: Record<string, unknown> | null
  simulated_timestamp: string | null
  created_at: string | null
}

export interface SimulationTelemetryRead {
  id: string
  simulation_id: string
  vehicle_id: string
  latitude: number
  longitude: number
  speed_kmph: number
  heading_degrees: number
  coordinates: [number, number]
  recorded_at: string
  source: string
}

export interface SimulationRead {
  id: string
  name: string
  seed: number
  status: SimulationStatus | string
  simulation_speed_multiplier: number
  simulated_time: string | null
  started_at: string | null
  paused_at: string | null
  resumed_at: string | null
  stopped_at: string | null
  created_by_user_id: string | null
  configuration: Record<string, unknown> | null
  total_vehicles: number
  created_at: string | null
  updated_at: string | null
}

export interface SimulationSummary {
  id: string
  name: string
  status: SimulationStatus | string
  speed_multiplier: number
  simulated_time: string | null
  total_vehicles: number
  queued_vehicles: number
  en_route_vehicles: number
  arrived_vehicles: number
  average_progress_percentage: number
  total_telemetry_points: number
  total_events: number
  started_at: string | null
  elapsed_simulated_seconds: number | null
  data_source: string
}

export interface SimulationWsMessage {
  event: SimulationEventType | string
  simulation_id: string
  status?: string
  simulated_time?: string
  speed_multiplier?: number
  vehicle_id?: string
  latitude?: number
  longitude?: number
  progress_percentage?: number
  speed_kmph?: number
  heading_degrees?: number
}


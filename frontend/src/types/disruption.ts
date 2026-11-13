export type DisruptionType =
  | 'VEHICLE_BREAKDOWN'
  | 'TRAFFIC_CONGESTION'
  | 'WAREHOUSE_SHUTDOWN'
  | 'DEMAND_SURGE'
  | 'DELIVERY_DELAY'

export type DisruptionSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type DisruptionStatus = 'DETECTED' | 'ACTIVE' | 'MONITORING' | 'RESOLVED' | 'CANCELLED'
export type AffectedResourceType = 'VEHICLE' | 'ORDER' | 'WAREHOUSE' | 'NETWORK_EDGE'

export interface DisruptionImpactRead {
  id: string
  disruption_id: string
  affected_resource_type: AffectedResourceType | string
  affected_resource_id: string
  impact_category: string
  severity: DisruptionSeverity | string
  estimated_delay_minutes: number | null
  impact_details: Record<string, unknown> | null
  detected_at: string
}

export interface DisruptionEventRead {
  id: string
  disruption_id: string
  event_type: string
  previous_status: string | null
  new_status: string | null
  event_data: Record<string, unknown> | null
  performed_by_user_id: string | null
  created_at: string
}

export interface DisruptionCreate {
  disruption_type: DisruptionType
  title: string
  description?: string
  severity?: DisruptionSeverity
  simulation_id?: string | null
  affected_vehicle_id?: string | null
  affected_warehouse_id?: string | null
  affected_network_edge_id?: string | null
  affected_order_id?: string | null
  location_latitude?: number | null
  location_longitude?: number | null
  parameters?: Record<string, unknown>
  start_time?: string | null
  expected_end_time?: string | null
}

export interface DisruptionResolveRequest {
  notes?: string | null
  actual_end_time?: string | null
}

export interface DisruptionCancelRequest {
  reason?: string | null
}

export interface DisruptionSummary {
  id: string
  disruption_code: string
  disruption_type: DisruptionType | string
  severity: DisruptionSeverity | string
  status: DisruptionStatus | string
  title: string
  simulation_id: string | null
  affected_vehicle_id: string | null
  affected_warehouse_id: string | null
  affected_network_edge_id: string | null
  affected_order_id: string | null
  start_time: string
  expected_end_time: string | null
  actual_end_time: string | null
  created_at: string
  updated_at: string
}

export interface DisruptionRead extends DisruptionSummary {
  description: string | null
  location_latitude: number | null
  location_longitude: number | null
  parameters: Record<string, unknown> | null
  created_by_user_id: string | null
  resolved_by_user_id: string | null
  impacts: DisruptionImpactRead[]
  events: DisruptionEventRead[]
}

export interface DisruptionAnalysisReport {
  disruption_id: string
  disruption_code: string
  disruption_type: string
  severity: string
  status: string
  affected_vehicles_count: number
  affected_orders_count: number
  urgent_orders_count: number
  overdue_orders_count: number
  at_risk_orders_count: number
  affected_warehouses_count: number
  affected_network_edges_count: number
  total_estimated_delay_minutes: number
  affected_vehicles: Array<{
    vehicle_id: string
    vehicle_code: string
    registration_number: string | null
    status: string
    current_load_kg: number
    impact_category: string
    severity: string
    estimated_delay_minutes: number | null
  }>
  affected_orders: Array<{
    order_id: string
    order_number: string
    status: string
    priority: string
    sla_hours: number | null
    expected_delivery_at: string | null
    estimated_delay_minutes: number | null
    is_at_risk: boolean
    is_overdue: boolean
    customer_name: string | null
  }>
  at_risk_orders: Array<{
    order_id: string
    order_number: string
    status: string
    priority: string
    expected_delivery_at: string | null
    estimated_delay_minutes: number
    risk_level: string
  }>
  analyzed_at: string
}


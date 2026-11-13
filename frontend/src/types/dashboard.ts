export interface NetworkKPIs {
  total_warehouses: number
  total_customers: number
  total_network_connections: number
  operational_warehouses: number | null
  total_storage_capacity: number | null
  used_storage_capacity: number | null
}

export interface OperationalKPIs {
  total_vehicles: number | null
  active_vehicles: number | null
  in_transit_vehicles: number | null
  total_orders: number | null
  pending_orders: number | null
  in_transit_orders: number | null
  delivered_orders: number | null
  delayed_orders: number | null
}

export interface SimulationKPIs {
  active_simulations: number
  completed_simulations: number
}

export interface PerformanceKPIs {
  on_time_delivery_rate: number | null
  fleet_utilization: number | null
  average_delivery_time_minutes: number | null
}

export interface DisruptionKPIs {
  total_disruptions: number
  active_disruptions: number
  critical_disruptions: number
  affected_vehicles_count: number
  affected_orders_count: number
}

export interface DashboardSummaryResponse {
  network: NetworkKPIs
  operations: OperationalKPIs
  simulations: SimulationKPIs
  disruptions: DisruptionKPIs | null
  performance: PerformanceKPIs
  overview_summary: Record<string, unknown> | null
  order_summary: Record<string, unknown> | null
  fleet_summary: Record<string, unknown> | null
  warehouse_summary: Record<string, unknown> | null
  disruption_summary: Record<string, unknown> | null
  agent_summary: Record<string, unknown> | null
  recovery_summary: Record<string, unknown> | null
  simulation_summary: Record<string, unknown> | null
  generated_at: string
  data_source: 'SIMULATED' | string
  notes: string
}


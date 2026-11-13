export type TrendGrouping = 'DAY' | 'WEEK' | 'MONTH'

export type ReportType =
  | 'EXECUTIVE_SUMMARY'
  | 'FLEET_PERFORMANCE'
  | 'WAREHOUSE_PERFORMANCE'
  | 'DISRUPTION_REPORT'
  | 'AI_INTELLIGENCE_REPORT'
  | 'RECOVERY_PERFORMANCE'
  | 'SIMULATION_REPORT'

export type ReportStatus = 'PENDING' | 'GENERATING' | 'COMPLETED' | 'FAILED' | 'EXPIRED'

export interface AnalyticsFilterMeta {
  start_date: string | null
  end_date: string | null
  simulation_id: string | null
  include_simulations: boolean
  data_scope: string
  generated_at: string
}

export interface OverviewAnalyticsResponse {
  total_orders: number
  delivered_orders: number
  in_transit_orders: number
  overdue_orders: number
  estimated_delayed_orders: number
  cancelled_orders: number
  delivery_success_rate: number
  on_time_delivery_rate: number
  total_vehicles: number
  active_vehicles: number
  fleet_utilization_rate: number
  total_warehouses: number
  warehouse_utilization_rate: number
  active_disruptions: number
  resolved_disruptions: number
  total_agent_runs: number
  total_recovery_plans: number
  executed_recovery_plans: number
  recovery_success_rate: number
  active_simulations: number
  metric_classifications: Record<string, string>
  unavailable_metrics: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface OrderAnalyticsResponse {
  total_orders: number
  orders_by_status: Record<string, number>
  orders_by_priority: Record<string, number>
  delivered_orders: number
  cancelled_orders: number
  in_transit_orders: number
  overdue_orders: number
  estimated_delayed_orders: number
  eligible_orders: number
  on_time_delivered_orders: number
  late_delivered_orders: number
  delivery_success_rate: number
  on_time_delivery_rate: number
  average_delivery_duration_minutes: number | null
  average_estimated_delay_minutes: number | null
  total_order_weight_kg: number
  total_order_value: number
  metric_classifications: Record<string, string>
  unavailable_metrics: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface VehiclePerformanceSummary {
  vehicle_id: string
  vehicle_code: string
  registration_number: string
  vehicle_type: string
  status: string
  capacity_kg: number
  current_load_kg: number
  load_utilization_percentage: number
  assigned_orders_count: number
  distance_travelled_km: number | null
  distance_data_source: string
}

export interface FleetAnalyticsResponse {
  total_vehicles: number
  available_vehicles: number
  in_transit_vehicles: number
  idle_vehicles: number
  breakdown_vehicles: number
  maintenance_vehicles: number
  offline_vehicles: number
  vehicles_by_status: Record<string, number>
  vehicles_by_type: Record<string, number>
  total_fleet_capacity_kg: number
  total_current_load_kg: number
  average_load_utilization_percentage: number
  fleet_capacity_utilization_percentage: number
  active_vehicle_utilization_rate: number
  total_distance_travelled_km: number | null
  average_distance_per_vehicle_km: number | null
  vehicles: VehiclePerformanceSummary[]
  metric_classifications: Record<string, string>
  unavailable_metrics: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface DisruptionAnalyticsResponse {
  total_disruptions: number
  active_disruptions: number
  resolved_disruptions: number
  cancelled_disruptions: number
  disruptions_by_status: Record<string, number>
  disruptions_by_severity: Record<string, number>
  disruptions_by_type: Record<string, number>
  affected_vehicles_count: number
  affected_orders_count: number
  affected_warehouses_count: number
  affected_edges_count: number
  average_resolution_time_minutes: number | null
  estimated_total_delay_minutes: number
  metric_classifications: Record<string, string>
  unavailable_metrics: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface AgentAnalyticsResponse {
  total_agent_runs: number
  completed_runs: number
  partially_completed_runs: number
  failed_runs: number
  ai_unavailable_runs: number
  runs_by_status: Record<string, number>
  total_agent_executions: number
  executions_by_status: Record<string, number>
  executions_by_agent_name: Record<string, number>
  provider_usage_distribution: Record<string, number>
  total_recommendations: number
  validated_recommendations: number
  rejected_recommendations: number
  requires_validation_recommendations: number
  informational_recommendations: number
  recommendations_by_validation_status: Record<string, number>
  recommendations_by_type: Record<string, number>
  average_agent_execution_duration_ms: number | null
  average_run_duration_ms: number | null
  average_confidence_score: number | null
  agent_success_rate: number
  token_usage_total: number | null
  estimated_llm_cost_usd: number | null
  metric_classifications: Record<string, string>
  unavailable_metrics: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface RecoveryAnalyticsResponse {
  total_recovery_plans: number
  optimized_plans: number
  pending_approval_plans: number
  approved_plans: number
  rejected_plans: number
  executed_plans: number
  partially_executed_plans: number
  failed_plans: number
  infeasible_plans: number
  plans_by_status: Record<string, number>
  plans_by_strategy: Record<string, number>
  total_affected_orders_in_plans: number
  total_reassigned_orders_proposed: number
  total_recovered_orders: number
  total_recovery_actions: number
  executed_actions: number
  failed_actions: number
  pending_actions: number
  recovery_success_rate: number
  average_recovery_execution_time_minutes: number | null
  estimated_delay_reduction_minutes: number
  estimated_distance_change_km: number
  estimated_cost_change: number
  metric_classifications: Record<string, string>
  unavailable_metrics: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface TrendPoint {
  period: string
  value: number
  count: number
  secondary_value: number | null
  breakdown: Record<string, unknown> | null
}

export interface TrendSeriesResponse {
  domain: string
  metric_name: string
  grouping: TrendGrouping
  unit: string
  data_points: TrendPoint[]
  total_points: number
  is_historical: boolean
  notes: string | null
  filter_meta: AnalyticsFilterMeta
}

export interface ComparisonMetricItem {
  metric_name: string
  label: string
  before_value: number | null
  after_value: number | null
  absolute_difference: number | null
  percentage_change: number | null
  improvement_direction: 'LOWER_IS_BETTER' | 'HIGHER_IS_BETTER' | 'NEUTRAL'
  is_improved: boolean | null
  unit: string
  data_classification: string
}

export interface PerformanceComparisonResponse {
  comparison_scope: string
  disruption_id: string | null
  recovery_plan_id: string | null
  simulation_id: string | null
  total_comparisons_evaluated: number
  metrics: ComparisonMetricItem[]
  notes: string[]
  filter_meta: AnalyticsFilterMeta
}

export interface AnalyticsHealthResponse {
  status: string
  analytics_engine: string
  pdf_reporting_engine: string
  reportlab_available: boolean
  reports_storage_ready: boolean
  database_connected: boolean
  total_generated_reports: number
  timestamp: string
}

export interface ReportGenerateRequest {
  report_type: ReportType
  title?: string
  start_date?: string
  end_date?: string
  simulation_id?: string
  include_simulations?: boolean
  include_charts?: boolean
  filters?: Record<string, unknown>
}

export interface ReportMetadataRead {
  id: string
  report_code: string
  report_type: ReportType | string
  title: string
  status: ReportStatus | string
  requested_by_user_id: string | null
  simulation_id: string | null
  include_simulations: boolean
  start_date: string | null
  end_date: string | null
  filters: Record<string, unknown> | null
  summary_metrics: Record<string, unknown> | null
  include_charts: boolean
  file_reference: string | null
  file_name: string | null
  file_size: number | null
  generated_at: string | null
  expires_at: string | null
  error_message: string | null
  created_at: string
}

export interface ReportTypeInfo {
  report_type: ReportType | string
  title: string
  description: string
  included_sections: string[]
}

export interface ReportTypesListResponse {
  report_types: ReportTypeInfo[]
  total: number
}


export type RecoveryPlanStatus =
  | 'DRAFT'
  | 'OPTIMIZING'
  | 'OPTIMIZED'
  | 'VALIDATION_FAILED'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXECUTING'
  | 'EXECUTED'
  | 'PARTIALLY_EXECUTED'
  | 'FAILED'
  | 'EXPIRED'

export type OptimizationStrategy =
  | 'SINGLE_VEHICLE_RECOVERY'
  | 'MULTI_VEHICLE_RECOVERY'
  | 'PRIORITY_BASED_RECOVERY'
  | 'ALTERNATIVE_ROUTE_RECOVERY'
  | 'PARTIAL_RECOVERY'

export interface RecoveryPlanGenerateRequest {
  disruption_id: string
  simulation_id?: string | null
  optimization_strategy?: OptimizationStrategy
  weights?: Record<string, number>
  max_replacement_vehicles?: number
}

export interface RecoveryPlanApproveRequest {
  notes?: string
}

export interface RecoveryPlanRejectRequest {
  reason: string
}

export interface RecoveryAssignmentRead {
  id: string
  recovery_plan_id: string
  order_id: string
  previous_vehicle_id: string | null
  proposed_vehicle_id: string
  origin_node_id: string
  destination_node_id: string
  proposed_route_node_ids: string[]
  proposed_route_edge_ids: string[]
  estimated_distance_km: number
  estimated_travel_time_minutes: number
  estimated_delay_minutes: number
  order_priority: string
  assignment_reason: string | null
  validation_status: string
  created_at: string
}

export interface RecoveryActionRead {
  id: string
  recovery_plan_id: string
  action_type: string
  target_resource_type: string
  target_resource_id: string
  action_payload: Record<string, unknown> | null
  status: string
  execution_result: Record<string, unknown> | null
  error_message: string | null
  executed_at: string | null
  created_at: string
}

export interface RecoveryAuditLogRead {
  id: string
  recovery_plan_id: string
  action: string
  previous_status: string | null
  new_status: string
  performed_by_user_id: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export interface RecoveryComparisonRead {
  id: string
  recovery_plan_id: string
  metric_name: string
  baseline_value: number
  proposed_value: number
  improvement_value: number
  improvement_percentage: number
  unit: string
  created_at: string
}

export interface RecoveryPlanRead {
  id: string
  recovery_code: string
  disruption_id: string
  simulation_id: string | null
  agent_run_id: string | null
  status: RecoveryPlanStatus | string
  optimization_strategy: OptimizationStrategy | string
  objective_value: number | null
  estimated_total_distance_km: number
  estimated_total_travel_time_minutes: number
  estimated_total_delay_minutes: number
  estimated_recovery_cost: number
  affected_order_count: number
  reassigned_order_count: number
  assigned_vehicle_count: number
  optimization_metadata: Record<string, unknown> | null
  created_by_user_id: string | null
  approved_by_user_id: string | null
  approved_at: string | null
  executed_at: string | null
  rejected_at: string | null
  rejection_reason: string | null
  created_at: string
  updated_at: string
  assignments: RecoveryAssignmentRead[]
  comparisons: RecoveryComparisonRead[]
}

export interface RecoveryPlanValidationReport {
  plan_id: string
  recovery_code: string
  is_valid: boolean
  status: string
  checked_constraints: string[]
  violations: string[]
  validated_at: string
}

export interface RecoveryKPISummary {
  total_recovery_plans: number
  pending_approval_count: number
  approved_count: number
  executed_count: number
  rejected_count: number
  total_orders_recovered: number
  average_delay_reduction_pct: number
  total_travel_time_saved_minutes: number
}


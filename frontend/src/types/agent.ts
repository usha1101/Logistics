export type AgentRunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'PARTIALLY_COMPLETED'
  | 'FAILED'
  | 'AI_UNAVAILABLE'

export type AgentExecutionStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED'
export type RecommendationPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type RecommendationValidationStatus =
  | 'VALIDATED'
  | 'REQUIRES_VALIDATION'
  | 'REJECTED'
  | 'INFORMATIONAL'

export interface AgentRecommendationRead {
  id: string
  agent_run_id: string
  source_agent: string
  recommendation_type: string
  priority: RecommendationPriority | string
  title: string
  description: string
  target_resource_type: string | null
  target_resource_id: string | null
  evidence: Record<string, unknown> | null
  validation_status: RecommendationValidationStatus | string
  execution_status: string
  created_at: string
}

export interface AgentExecutionRead {
  id: string
  agent_run_id: string
  agent_name: string
  status: AgentExecutionStatus | string
  provider: string
  model: string
  input_summary: string | null
  output: Record<string, unknown> | null
  confidence_score: number | null
  evidence_references: Array<Record<string, unknown>> | null
  warnings: string[] | null
  execution_duration_ms: number | null
  started_at: string
  completed_at: string | null
}

export interface AgentRunRead {
  id: string
  disruption_id: string
  simulation_id: string | null
  status: AgentRunStatus | string
  primary_provider: string
  started_at: string
  completed_at: string | null
  execution_duration_ms: number | null
  error_summary: string | null
  created_by_user_id: string | null
  created_at: string
  executions: AgentExecutionRead[]
  recommendations: AgentRecommendationRead[]
}

export interface ProviderStatusResponse {
  gemini_configured: boolean
  groq_configured: boolean
  primary_provider: string
  fallback_provider: string
  primary_model: string
  fallback_model: string
  timeout_seconds: number
  max_retries: number
}


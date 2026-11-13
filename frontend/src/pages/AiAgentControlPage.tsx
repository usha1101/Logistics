import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Cpu, Play, RotateCw, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'

import { KpiCard } from '@/components/ui/KpiCard'
import { EmptyState, ErrorState, LoadingState, UnavailableNotice } from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ACTION_PERMISSIONS, hasAnyRole } from '@/config/permissions'
import { formatDateTimeShort, getApiErrorMessage } from '@/lib/formatters'
import { agentService } from '@/services/agent.service'
import { disruptionService } from '@/services/disruption.service'
import { useAuth } from '@/stores/auth-context'

const SPECIALIST_AGENTS = [
  { key: 'DISRUPTION_ANALYSIS', title: 'Disruption Analysis Agent' },
  { key: 'FLEET_INTELLIGENCE', title: 'Fleet Intelligence Agent' },
  { key: 'ROUTING_INTELLIGENCE', title: 'Routing Intelligence Agent' },
  { key: 'WAREHOUSE_INTELLIGENCE', title: 'Warehouse Intelligence Agent' },
  { key: 'ORDER_PRIORITY', title: 'Order Priority Agent' },
  { key: 'COORDINATOR_SYNTHESIS', title: 'Coordinator Agent' },
]

export function AiAgentControlPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const canTriggerAgents = hasAnyRole(user?.role, ACTION_PERMISSIONS.AGENT_TRIGGER)

  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedDisruptionId, setSelectedDisruptionId] = useState<string>('')
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const providerQuery = useQuery({
    queryKey: ['agents', 'status'],
    queryFn: () => agentService.getProviderStatus(),
  })

  const runsQuery = useQuery({
    queryKey: ['agents', 'runs', statusFilter],
    queryFn: () =>
      agentService.listRuns({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        page: 1,
        page_size: 20,
      }),
    refetchInterval: 10_000,
  })

  const disruptionsQuery = useQuery({
    queryKey: ['disruptions', 'agents-ref'],
    queryFn: () => disruptionService.listDisruptions({ page: 1, page_size: 30 }),
  })

  const analyzeMutation = useMutation({
    mutationFn: (disruptionId: string) => agentService.analyzeDisruption(disruptionId),
    onSuccess: (run) => {
      setActionErr(null)
      setActionMsg(`Triggered multi-agent run ${run.id.slice(0, 8)} (${run.status}).`)
      setSelectedRunId(run.id)
      void queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const retryMutation = useMutation({
    mutationFn: (runId: string) => agentService.retryRun(runId),
    onSuccess: (run) => {
      setActionErr(null)
      setActionMsg(`Retried run ${run.id.slice(0, 8)} -> ${run.status}.`)
      setSelectedRunId(run.id)
      void queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const runs = runsQuery.data?.items ?? []
  const activeRun = useMemo(
    () => runs.find((r) => r.id === selectedRunId) ?? runs[0] ?? null,
    [runs, selectedRunId],
  )

  const executionByAgent = useMemo(() => {
    const map = new Map<string, NonNullable<typeof activeRun>['executions'][number]>()
    for (const ex of activeRun?.executions ?? []) {
      map.set(ex.agent_name, ex)
    }
    return map
  }, [activeRun])

  if (runsQuery.isLoading) {
    return <LoadingState message="Loading AI Agent Control Centre..." />
  }

  if (runsQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(runsQuery.error)}
        onRetry={() => void runsQuery.refetch()}
      />
    )
  }

  const provider = providerQuery.data
  const completedCount = runs.filter((r) => r.status === 'COMPLETED').length
  const totalRecommendations = runs.reduce((acc, r) => acc + r.recommendations.length, 0)

  return (
    <div className="space-y-6">
      {/* Provider Status & Analysis Trigger Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
        <div className="flex flex-wrap items-center gap-3 text-xs font-telemetry">
          <span className="inline-flex items-center gap-1.5 text-lime font-bold">
            <span className="h-2 w-2 rounded-full bg-lime animate-pulse" />
            PRIMARY: {provider?.primary_provider.toUpperCase() ?? 'LOADING'} (
            {provider?.primary_model ?? '—'})
          </span>
          <span className="text-secondary">
            Fallback: {provider?.fallback_provider ?? '—'} (
            {provider?.gemini_configured || provider?.groq_configured ? 'Keys Ready' : 'No API Keys — Safe Fallback'})
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-1.5 text-primary"
          >
            <option value="ALL">Run Status: All</option>
            <option value="COMPLETED">COMPLETED</option>
            <option value="PARTIALLY_COMPLETED">PARTIALLY_COMPLETED</option>
            <option value="AI_UNAVAILABLE">AI_UNAVAILABLE</option>
            <option value="FAILED">FAILED</option>
          </select>

          {canTriggerAgents && (
            <div className="flex items-center gap-1.5">
              <select
                value={selectedDisruptionId || disruptionsQuery.data?.items[0]?.id || ''}
                onChange={(e) => setSelectedDisruptionId(e.target.value)}
                className="max-w-[220px] rounded border border-surface-container-highest bg-surface-container px-2.5 py-1.5 text-primary"
              >
                {(disruptionsQuery.data?.items ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.disruption_code} — {d.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={
                  analyzeMutation.isPending ||
                  !(selectedDisruptionId || disruptionsQuery.data?.items[0]?.id)
                }
                onClick={() =>
                  analyzeMutation.mutate(
                    selectedDisruptionId || disruptionsQuery.data!.items[0]!.id,
                  )
                }
                className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3 py-1.5 font-display font-bold text-on-primary-fixed hover:bg-primary-fixed-dim disabled:opacity-40"
              >
                <Play className="h-3.5 w-3.5" />
                {analyzeMutation.isPending ? 'Analyzing...' : 'Run AI Analysis'}
              </button>
            </div>
          )}
        </div>
      </div>

      {actionMsg && (
        <div className="rounded border border-primary-fixed/40 bg-primary-fixed/10 px-4 py-2 text-xs text-lime">
          {actionMsg}
        </div>
      )}
      {actionErr && (
        <div className="rounded border border-[#EF4444]/40 bg-[#93000a]/25 px-4 py-2 text-xs text-error">
          {actionErr}
        </div>
      )}

      {/* 3 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          label="Specialist Agents"
          value={SPECIALIST_AGENTS.length}
          sublabel="Disruption, Fleet, Routing, Warehouse, Order, Coordinator"
          icon={<Bot className="h-4 w-4" />}
        />
        <KpiCard
          label="Agent Runs Logged"
          value={runsQuery.data?.total ?? runs.length}
          sublabel={`${completedCount} completed in current view`}
          accent="lime"
          icon={<Cpu className="h-4 w-4" />}
        />
        <KpiCard
          label="Validated Recommendations"
          value={totalRecommendations}
          sublabel="Generated across retrieved agent runs"
          icon={<ShieldCheck className="h-4 w-4" />}
        />
      </section>

      {/* 3x2 Operational Agent Swarm Grid */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-base font-bold text-primary">
            Operational Agent Swarm {activeRun ? `— Run ${activeRun.id.slice(0, 8)}` : ''}
          </h2>
          {activeRun && canTriggerAgents && (
            <button
              type="button"
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate(activeRun.id)}
              className="inline-flex items-center gap-1.5 rounded border border-surface-container-highest bg-surface-container px-3 py-1 font-telemetry text-xs text-primary hover:border-lime"
            >
              <RotateCw className="h-3.5 w-3.5" />
              Retry Run
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {SPECIALIST_AGENTS.map((agent) => {
            const isCoordinator = agent.key === 'COORDINATOR_SYNTHESIS'
            const exec = isCoordinator ? undefined : executionByAgent.get(agent.key)
            const cardStatus = isCoordinator
              ? activeRun?.status ?? 'STANDBY'
              : exec?.status ?? 'STANDBY'
            const cardModel = isCoordinator
              ? `${activeRun?.primary_provider ?? provider?.primary_provider ?? 'deterministic'} coordinator`
              : exec?.model ?? provider?.primary_model ?? '—'
            const cardDuration = isCoordinator
              ? activeRun?.execution_duration_ms
              : exec?.execution_duration_ms
            const cardSummary = isCoordinator
              ? activeRun
                ? `Synthesized ${activeRun.recommendations.length} validated recommendation(s) across ${activeRun.executions.length} specialist agents.`
                : 'Awaiting disruption analysis run.'
              : (exec?.output?.summary as string | undefined) ??
                exec?.input_summary ??
                'Awaiting disruption analysis run.'

            return (
              <div
                key={agent.key}
                className={`rounded-lg border p-4 space-y-2 ${
                  cardStatus === 'COMPLETED'
                    ? 'border-primary-fixed/40 bg-surface-container-low'
                    : 'border-surface-container-highest bg-surface-container-low'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-display text-sm font-bold text-primary">{agent.title}</span>
                  <StatusBadge value={cardStatus} />
                </div>
                <div className="flex items-center justify-between font-telemetry text-[11px] text-secondary">
                  <span>Model: {cardModel}</span>
                  <span>
                    {exec?.confidence_score !== null && exec?.confidence_score !== undefined
                      ? `Conf ${(exec.confidence_score * 100).toFixed(0)}%`
                      : isCoordinator && activeRun
                        ? `${activeRun.recommendations.length} recs`
                        : '—'}
                  </span>
                </div>
                <p className="text-xs text-secondary line-clamp-2">{cardSummary}</p>
                {cardDuration !== null && cardDuration !== undefined && (
                  <div className="font-telemetry text-[10px] text-lime">
                    Duration: {Math.round(cardDuration)} ms
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* Lower Split: Recommendations Feed (7 cols) & Run History Timeline (5 cols) */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
          <h3 className="font-display text-sm font-bold text-primary">
            Autonomous Recommendations ({activeRun?.recommendations.length ?? 0})
          </h3>
          <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
            {(activeRun?.recommendations ?? []).map((rec) => (
              <div
                key={rec.id}
                className="rounded-md border border-surface-container-highest bg-surface-container p-3 space-y-1.5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-telemetry text-xs font-bold text-lime">
                    {rec.source_agent} • {rec.recommendation_type}
                  </span>
                  <div className="flex gap-1.5">
                    <StatusBadge value={rec.priority} />
                    <StatusBadge value={rec.validation_status} />
                  </div>
                </div>
                <h4 className="font-display text-sm font-semibold text-primary">{rec.title}</h4>
                <p className="text-xs text-secondary">{rec.description}</p>
              </div>
            ))}
            {(activeRun?.recommendations ?? []).length === 0 && (
              <EmptyState
                title="No recommendations in selected run"
                description="Trigger an AI analysis on a disruption to view structured recommendations."
              />
            )}
          </div>
        </div>

        <div className="lg:col-span-5 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
          <h3 className="font-display text-sm font-bold text-primary">
            Agent Runs Timeline ({runs.length})
          </h3>
          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {runs.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelectedRunId(r.id)}
                className={`w-full rounded-md border p-3 text-left transition-colors ${
                  activeRun?.id === r.id
                    ? 'border-primary-fixed bg-surface-container'
                    : 'border-surface-container-highest bg-surface-container-lowest hover:bg-surface-container'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-telemetry text-xs font-bold text-primary">
                    Run {r.id.slice(0, 8)} • {r.primary_provider}
                  </span>
                  <StatusBadge value={r.status} />
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-secondary">
                  <span>{r.recommendations.length} recommendations</span>
                  <span>{formatDateTimeShort(r.created_at)}</span>
                </div>
                {r.error_summary && (
                  <p className="mt-1 text-[11px] text-error truncate">{r.error_summary}</p>
                )}
              </button>
            ))}
          </div>

          {!canTriggerAgents && (
            <UnavailableNotice
              title="Trigger Restricted"
              description="ANALYST role has read-only access to AI agent runs and recommendations."
            />
          )}
        </div>
      </section>
    </div>
  )
}


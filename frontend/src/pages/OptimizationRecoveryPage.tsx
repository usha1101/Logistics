import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Play, Plus, Route as RouteIcon, ShieldCheck, XCircle } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import {
  BengaluruNetworkMap,
  type MapEdgeSegment,
  type MapNodePoint,
  type MapVehicleMarker,
} from '@/components/maps/BengaluruNetworkMap'
import { KpiCard } from '@/components/ui/KpiCard'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  UnavailableNotice,
} from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ACTION_PERMISSIONS, hasAnyRole } from '@/config/permissions'
import { formatDateTimeShort, getApiErrorMessage } from '@/lib/formatters'
import { disruptionService } from '@/services/disruption.service'
import { fleetService } from '@/services/fleet.service'
import { networkService } from '@/services/network.service'
import { recoveryService } from '@/services/recovery.service'
import { useAuth } from '@/stores/auth-context'
import type { DisruptionSeverity, DisruptionType } from '@/types/disruption'
import type { OptimizationStrategy } from '@/types/recovery'

export function OptimizationRecoveryPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const canOperateDisruptions = hasAnyRole(user?.role, ACTION_PERMISSIONS.DISRUPTION_OPERATE)
  const canGenerateRecovery = hasAnyRole(user?.role, ACTION_PERMISSIONS.RECOVERY_GENERATE)
  const canDecideRecovery = hasAnyRole(user?.role, ACTION_PERMISSIONS.RECOVERY_DECIDE)

  const [selectedDisruptionId, setSelectedDisruptionId] = useState<string | null>(null)
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [strategy, setStrategy] = useState<OptimizationStrategy>('MULTI_VEHICLE_RECOVERY')
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  const [newDisruptionModalOpen, setNewDisruptionModalOpen] = useState(false)
  const [newType, setNewType] = useState<DisruptionType>('VEHICLE_BREAKDOWN')
  const [newSeverity, setNewSeverity] = useState<DisruptionSeverity>('CRITICAL')
  const [newTitle, setNewTitle] = useState('')
  const [newVehicleId, setNewVehicleId] = useState('')

  const disruptionsQuery = useQuery({
    queryKey: ['disruptions', 'recovery-page'],
    queryFn: () => disruptionService.listDisruptions({ page: 1, page_size: 30 }),
    refetchInterval: 10_000,
  })

  const summaryQuery = useQuery({
    queryKey: ['recovery', 'summary'],
    queryFn: () => recoveryService.getSummary(),
    refetchInterval: 10_000,
  })

  const plansQuery = useQuery({
    queryKey: ['recovery', 'plans'],
    queryFn: () => recoveryService.listPlans({ page: 1, page_size: 30 }),
    refetchInterval: 10_000,
  })

  const availableVehiclesQuery = useQuery({
    queryKey: ['fleet', 'available', 'recovery'],
    queryFn: () => fleetService.listAvailableVehicles({ limit: 50 }),
    refetchInterval: 15_000,
  })

  const allVehiclesQuery = useQuery({
    queryKey: ['fleet', 'vehicles', 'recovery'],
    queryFn: () => fleetService.listVehicles({ limit: 100 }),
  })

  const geoJsonQuery = useQuery({
    queryKey: ['network', 'geojson', 'recovery'],
    queryFn: () => networkService.getGeoJson({ only_active: true }),
  })

  const disruptions = disruptionsQuery.data?.items ?? []
  const activeDisruption = useMemo(
    () =>
      disruptions.find((d) => d.id === selectedDisruptionId) ??
      disruptions.find((d) => d.status === 'ACTIVE') ??
      disruptions[0] ??
      null,
    [disruptions, selectedDisruptionId],
  )

  const impactQuery = useQuery({
    queryKey: ['disruptions', 'impact', activeDisruption?.id],
    queryFn: () => disruptionService.getImpactAnalysis(activeDisruption!.id),
    enabled: Boolean(activeDisruption?.id),
  })

  const plans = plansQuery.data?.items ?? []
  const activePlan = useMemo(
    () =>
      plans.find((p) => p.id === selectedPlanId) ??
      plans.find((p) => activeDisruption && p.disruption_id === activeDisruption.id) ??
      plans[0] ??
      null,
    [plans, selectedPlanId, activeDisruption],
  )

  const actionsQuery = useQuery({
    queryKey: ['recovery', 'actions', activePlan?.id],
    queryFn: () => recoveryService.getActions(activePlan!.id),
    enabled: Boolean(activePlan?.id),
  })

  const createDisruptionMutation = useMutation({
    mutationFn: () =>
      disruptionService.createDisruption({
        disruption_type: newType,
        severity: newSeverity,
        title: newTitle.trim(),
        affected_vehicle_id: newVehicleId || undefined,
      }),
    onSuccess: (created) => {
      setActionErr(null)
      setActionMsg(`Disruption ${created.disruption_code} created.`)
      setNewDisruptionModalOpen(false)
      setNewTitle('')
      setSelectedDisruptionId(created.id)
      void queryClient.invalidateQueries({ queryKey: ['disruptions'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const disruptionStateMutation = useMutation({
    mutationFn: async ({ id, op }: { id: string; op: 'activate' | 'resolve' }) =>
      op === 'activate'
        ? disruptionService.activateDisruption(id)
        : disruptionService.resolveDisruption(id, { notes: 'Resolved from Recovery Console' }),
    onSuccess: (updated) => {
      setActionErr(null)
      setActionMsg(`Disruption ${updated.disruption_code} -> ${updated.status}.`)
      void queryClient.invalidateQueries({ queryKey: ['disruptions'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const generatePlanMutation = useMutation({
    mutationFn: () =>
      recoveryService.generatePlan({
        disruption_id: activeDisruption!.id,
        simulation_id: activeDisruption?.simulation_id ?? null,
        optimization_strategy: strategy,
        max_replacement_vehicles: 5,
      }),
    onSuccess: (plan) => {
      setActionErr(null)
      setActionMsg(`Generated recovery plan ${plan.recovery_code} (${plan.status}).`)
      setSelectedPlanId(plan.id)
      void queryClient.invalidateQueries({ queryKey: ['recovery'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const planDecisionMutation = useMutation({
    mutationFn: async (op: 'validate' | 'approve' | 'execute' | 'reject') => {
      if (!activePlan) throw new Error('No recovery plan selected')
      if (op === 'validate') return recoveryService.validatePlan(activePlan.id)
      if (op === 'approve') return recoveryService.approvePlan(activePlan.id)
      if (op === 'execute') return recoveryService.executePlan(activePlan.id)
      return recoveryService.rejectPlan(activePlan.id, { reason: rejectReason.trim() })
    },
    onSuccess: () => {
      setActionErr(null)
      setActionMsg(`Recovery plan ${activePlan?.recovery_code ?? ''} action completed.`)
      setRejectModalOpen(false)
      setRejectReason('')
      void queryClient.invalidateQueries({ queryKey: ['recovery'] })
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['fleet'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const { mapNodes, mapEdges, recoveryPathCoords } = useMemo(() => {
    const features = geoJsonQuery.data?.features ?? []
    const nodeCoords = new Map<string, [number, number]>()
    const nodes: MapNodePoint[] = []
    const edges: MapEdgeSegment[] = []

    for (const f of features) {
      if (f.geometry.type === 'Point') {
        const [lon, lat] = f.geometry.coordinates as [number, number]
        nodeCoords.set(f.id, [lat, lon])
        nodes.push({
          id: f.id,
          name: String(f.properties.name ?? f.id),
          nodeType: String(f.properties.node_type ?? 'CUSTOMER'),
          latitude: lat,
          longitude: lon,
        })
      }
    }

    for (const f of features) {
      if (f.geometry.type === 'LineString') {
        const coords = f.geometry.coordinates as [number, number][]
        if (coords.length >= 2) {
          edges.push({
            id: f.id,
            from: [coords[0][1], coords[0][0]],
            to: [coords[coords.length - 1][1], coords[coords.length - 1][0]],
          })
        }
      }
    }

    const path: [number, number][] = []
    const firstAssignment = activePlan?.assignments[0]
    if (firstAssignment?.proposed_route_node_ids) {
      for (const nid of firstAssignment.proposed_route_node_ids) {
        const pt = nodeCoords.get(nid)
        if (pt) path.push(pt)
      }
    }

    return { mapNodes: nodes, mapEdges: edges, recoveryPathCoords: path }
  }, [geoJsonQuery.data, activePlan])

  const mapVehicles = useMemo<MapVehicleMarker[]>(() => {
    return (allVehiclesQuery.data?.items ?? [])
      .filter((v) => v.current_latitude !== null && v.current_longitude !== null)
      .map((v) => ({
        id: v.id,
        code: v.vehicle_code,
        status: v.status,
        latitude: v.current_latitude as number,
        longitude: v.current_longitude as number,
        speedKmph: v.current_speed_kmph,
        selected: activeDisruption?.affected_vehicle_id === v.id,
      }))
  }, [allVehiclesQuery.data, activeDisruption?.affected_vehicle_id])

  if (disruptionsQuery.isLoading || plansQuery.isLoading) {
    return <LoadingState message="Loading disruption impact & OR-Tools recovery plans..." />
  }

  if (disruptionsQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(disruptionsQuery.error)}
        onRetry={() => void disruptionsQuery.refetch()}
      />
    )
  }

  const summary = summaryQuery.data
  const impact = impactQuery.data
  const availableVehicles = availableVehiclesQuery.data?.items ?? []

  return (
    <div className="space-y-6">
      {/* Control Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select
            value={activeDisruption?.id ?? ''}
            onChange={(e) => {
              setSelectedDisruptionId(e.target.value)
              setSelectedPlanId(null)
            }}
            className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 font-semibold text-primary"
          >
            {disruptions.length === 0 && <option value="">No disruptions recorded</option>}
            {disruptions.map((d) => (
              <option key={d.id} value={d.id}>
                {d.disruption_code} — {d.title} ({d.status})
              </option>
            ))}
          </select>

          {activeDisruption && <StatusBadge value={activeDisruption.severity} />}
          {activeDisruption && <StatusBadge value={activeDisruption.status} />}
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {canOperateDisruptions && (
            <button
              type="button"
              onClick={() => setNewDisruptionModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 font-display font-semibold text-primary hover:border-lime"
            >
              <Plus className="h-3.5 w-3.5" />
              Report Disruption
            </button>
          )}

          {canGenerateRecovery && activeDisruption && (
            <>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as OptimizationStrategy)}
                className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-1.5 text-primary"
              >
                <option value="MULTI_VEHICLE_RECOVERY">MULTI_VEHICLE_RECOVERY</option>
                <option value="SINGLE_VEHICLE_RECOVERY">SINGLE_VEHICLE_RECOVERY</option>
                <option value="PRIORITY_BASED_RECOVERY">PRIORITY_BASED_RECOVERY</option>
                <option value="ALTERNATIVE_ROUTE_RECOVERY">ALTERNATIVE_ROUTE_RECOVERY</option>
                <option value="PARTIAL_RECOVERY">PARTIAL_RECOVERY</option>
              </select>
              <button
                type="button"
                disabled={generatePlanMutation.isPending}
                onClick={() => generatePlanMutation.mutate()}
                className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3 py-1.5 font-display font-bold text-on-primary-fixed hover:bg-primary-fixed-dim disabled:opacity-40"
              >
                <RouteIcon className="h-3.5 w-3.5" />
                {generatePlanMutation.isPending ? 'Optimizing...' : 'Generate Recovery Plan'}
              </button>
            </>
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

      {/* Main Split: Tactical Map (8 cols) + Disruption & Recovery Execution (4 cols) */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-display font-bold uppercase tracking-wider text-outline">
              Recovery Corridor Map (Bengaluru Network)
            </span>
            {recoveryPathCoords.length > 0 && (
              <span className="font-telemetry text-lime">
                Showing OR-Tools proposed route in cyber-lime
              </span>
            )}
          </div>
          <BengaluruNetworkMap
            nodes={mapNodes}
            edges={mapEdges}
            vehicles={mapVehicles}
            highlightedPath={recoveryPathCoords}
            heightClass="h-[460px]"
          />
        </div>

        <div className="lg:col-span-4 space-y-4">
          {/* Disruption Impact Card */}
          <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-sm font-bold text-primary">Breakdown &amp; Impact</h2>
              {activeDisruption && canOperateDisruptions && (
                <div className="flex gap-1.5">
                  {activeDisruption.status === 'DETECTED' && (
                    <button
                      type="button"
                      onClick={() =>
                        disruptionStateMutation.mutate({ id: activeDisruption.id, op: 'activate' })
                      }
                      className="rounded bg-surface-container-high px-2 py-1 text-lime"
                    >
                      Activate
                    </button>
                  )}
                  {['ACTIVE', 'MONITORING'].includes(activeDisruption.status) && (
                    <button
                      type="button"
                      onClick={() =>
                        disruptionStateMutation.mutate({ id: activeDisruption.id, op: 'resolve' })
                      }
                      className="rounded bg-[#22C55E]/20 px-2 py-1 text-[#22C55E]"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              )}
            </div>

            {impact ? (
              <div className="grid grid-cols-2 gap-2 font-telemetry">
                <div className="rounded bg-surface-container p-2">
                  <span className="text-[10px] text-outline block">Affected Vehicles</span>
                  <span className="font-bold text-primary">{impact.affected_vehicles_count}</span>
                </div>
                <div className="rounded bg-surface-container p-2">
                  <span className="text-[10px] text-outline block">Affected Orders</span>
                  <span className="font-bold text-[#FBBF24]">{impact.affected_orders_count}</span>
                </div>
                <div className="rounded bg-surface-container p-2">
                  <span className="text-[10px] text-outline block">Overdue Orders</span>
                  <span className="font-bold text-[#F87171]">{impact.overdue_orders_count}</span>
                </div>
                <div className="rounded bg-surface-container p-2">
                  <span className="text-[10px] text-outline block">Est. Delay</span>
                  <span className="font-bold text-primary">
                    {impact.total_estimated_delay_minutes.toFixed(0)} mins
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-secondary">Select a disruption to view impact analysis.</p>
            )}
          </div>

          {/* Recovery Recommendation & Execution Card */}
          <div className="rounded-lg border border-primary-fixed/40 bg-surface-container-low p-4 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-sm font-bold text-primary">
                Recovery Plan {activePlan ? `(${activePlan.recovery_code})` : ''}
              </h2>
              {activePlan && <StatusBadge value={activePlan.status} />}
            </div>

            {activePlan ? (
              <>
                <div className="grid grid-cols-2 gap-2 font-telemetry">
                  <div className="rounded bg-surface-container p-2">
                    <span className="text-[10px] text-outline block">Orders Reassigned</span>
                    <span className="font-bold text-lime">
                      {activePlan.reassigned_order_count} / {activePlan.affected_order_count}
                    </span>
                  </div>
                  <div className="rounded bg-surface-container p-2">
                    <span className="text-[10px] text-outline block">Est. Distance</span>
                    <span className="font-bold text-primary">
                      {activePlan.estimated_total_distance_km.toFixed(1)} km
                    </span>
                  </div>
                </div>

                {activePlan.comparisons.length > 0 && (
                  <div className="space-y-1 rounded bg-surface-container-lowest p-2.5">
                    {activePlan.comparisons.map((cmp) => (
                      <div key={cmp.id} className="flex justify-between font-telemetry text-[11px]">
                        <span className="text-secondary">{cmp.metric_name}</span>
                        <span className="text-lime">
                          {cmp.baseline_value.toFixed(1)} -&gt; {cmp.proposed_value.toFixed(1)}{' '}
                          {cmp.unit}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <div className="space-y-2 pt-1">
                  {canGenerateRecovery && (
                    <button
                      type="button"
                      disabled={planDecisionMutation.isPending}
                      onClick={() => planDecisionMutation.mutate('validate')}
                      className="flex w-full items-center justify-center gap-1.5 rounded border border-surface-container-highest bg-surface-container py-2 font-display font-semibold text-primary hover:border-lime"
                    >
                      <ShieldCheck className="h-3.5 w-3.5 text-lime" />
                      Validate Constraints
                    </button>
                  )}

                  {canDecideRecovery ? (
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        type="button"
                        disabled={
                          planDecisionMutation.isPending ||
                          activePlan.status !== 'PENDING_APPROVAL'
                        }
                        onClick={() => planDecisionMutation.mutate('approve')}
                        className="flex items-center justify-center gap-1 rounded bg-[#22C55E]/20 py-2 font-display font-bold text-[#22C55E] disabled:opacity-40"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Approve
                      </button>
                      <button
                        type="button"
                        disabled={
                          planDecisionMutation.isPending ||
                          !['PENDING_APPROVAL', 'APPROVED'].includes(activePlan.status)
                        }
                        onClick={() => setRejectModalOpen(true)}
                        className="flex items-center justify-center gap-1 rounded bg-[#EF4444]/20 py-2 font-display font-bold text-[#F87171] disabled:opacity-40"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Reject
                      </button>
                      <button
                        type="button"
                        disabled={
                          planDecisionMutation.isPending || activePlan.status !== 'APPROVED'
                        }
                        onClick={() => planDecisionMutation.mutate('execute')}
                        className="flex items-center justify-center gap-1 rounded bg-primary-fixed py-2 font-display font-bold text-on-primary-fixed disabled:opacity-40"
                      >
                        <Play className="h-3.5 w-3.5" />
                        Execute
                      </button>
                    </div>
                  ) : (
                    <UnavailableNotice
                      title="Approval / Execution Restricted"
                      description="Only ADMIN, OPERATIONS_MANAGER, or FLEET_MANAGER can approve, reject, or execute recovery plans."
                    />
                  )}
                </div>

                {(actionsQuery.data ?? []).length > 0 && (
                  <div className="border-t border-surface-container-highest pt-2 space-y-1">
                    <span className="text-[10px] font-bold uppercase text-outline">
                      Execution Actions
                    </span>
                    {actionsQuery.data!.map((a) => (
                      <div key={a.id} className="flex justify-between font-telemetry text-[11px]">
                        <span className="text-secondary">{a.action_type}</span>
                        <StatusBadge value={a.status} />
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <EmptyState
                title="No recovery plan generated"
                description="Click 'Generate Recovery Plan' to run OR-Tools optimization for the selected disruption."
              />
            )}
          </div>
        </div>
      </section>

      {/* Nearby / Available Replacement Vehicles + Recovery Plans Directory */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
          <h3 className="font-display text-sm font-bold text-primary">
            Available Replacement Vehicles ({availableVehicles.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-surface-container-highest bg-surface-container-lowest font-display text-[11px] uppercase text-outline">
                  <th className="px-3 py-2">Vehicle</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Free Capacity</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-highest/50">
                {availableVehicles.map((v) => (
                  <tr key={v.id}>
                    <td className="px-3 py-2 font-telemetry font-bold text-lime">{v.vehicle_code}</td>
                    <td className="px-3 py-2 text-secondary">{v.vehicle_type}</td>
                    <td className="px-3 py-2 font-telemetry text-primary">
                      {v.remaining_capacity_kg} / {v.capacity_kg} kg
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge value={v.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
          <h3 className="font-display text-sm font-bold text-primary">
            Recovery Plans Registry ({plans.length})
          </h3>
          <div className="space-y-2 max-h-60 overflow-y-auto pr-1 text-xs">
            {plans.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedPlanId(p.id)}
                className={`w-full rounded border p-2.5 text-left transition-colors ${
                  activePlan?.id === p.id
                    ? 'border-primary-fixed bg-surface-container'
                    : 'border-surface-container-highest bg-surface-container-lowest hover:bg-surface-container'
                }`}
              >
                <div className="flex justify-between">
                  <span className="font-telemetry font-bold text-lime">{p.recovery_code}</span>
                  <StatusBadge value={p.status} />
                </div>
                <div className="mt-1 flex justify-between text-secondary">
                  <span>{p.optimization_strategy}</span>
                  <span>{formatDateTimeShort(p.created_at)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom 3 Summary KPI Cards */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          label="Available Fleet Reserve"
          value={availableVehicles.length}
          sublabel="Vehicles ready for failover"
          accent="lime"
        />
        <KpiCard
          label="Total Plans / Pending Approval"
          value={`${summary?.total_recovery_plans ?? plans.length} / ${summary?.pending_approval_count ?? 0}`}
          sublabel={`${summary?.executed_count ?? 0} executed plans`}
        />
        <KpiCard
          label="Orders Recovered"
          value={summary?.total_orders_recovered ?? 0}
          sublabel={`Avg delay reduction: ${(summary?.average_delay_reduction_pct ?? 0).toFixed(1)}%`}
          accent="success"
        />
      </section>

      {/* Reject Reason Modal */}
      <Modal
        open={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject Recovery Plan"
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            planDecisionMutation.mutate('reject')
          }}
          className="space-y-3 text-xs"
        >
          <textarea
            required
            minLength={3}
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Enter audit rejection reason..."
            className="w-full rounded border border-surface-container-highest bg-surface-container p-3 text-primary"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setRejectModalOpen(false)}
              className="rounded bg-surface-container px-4 py-2 text-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={planDecisionMutation.isPending}
              className="rounded bg-[#EF4444] px-4 py-2 font-display font-bold text-white"
            >
              Confirm Reject
            </button>
          </div>
        </form>
      </Modal>

      {/* Create Disruption Modal */}
      <Modal
        open={newDisruptionModalOpen}
        onClose={() => setNewDisruptionModalOpen(false)}
        title="Report Operational Disruption"
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            createDisruptionMutation.mutate()
          }}
          className="space-y-3 text-xs"
        >
          <div>
            <label className="font-display text-[11px] uppercase text-secondary">Title</label>
            <input
              required
              minLength={3}
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Vehicle breakdown on Outer Ring Road"
              className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Type</label>
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value as DisruptionType)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                <option value="VEHICLE_BREAKDOWN">VEHICLE_BREAKDOWN</option>
                <option value="TRAFFIC_CONGESTION">TRAFFIC_CONGESTION</option>
                <option value="WAREHOUSE_SHUTDOWN">WAREHOUSE_SHUTDOWN</option>
                <option value="DEMAND_SURGE">DEMAND_SURGE</option>
                <option value="DELIVERY_DELAY">DELIVERY_DELAY</option>
              </select>
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Severity</label>
              <select
                value={newSeverity}
                onChange={(e) => setNewSeverity(e.target.value as DisruptionSeverity)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
            </div>
          </div>
          {newType === 'VEHICLE_BREAKDOWN' && (
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Affected Vehicle
              </label>
              <select
                value={newVehicleId}
                onChange={(e) => setNewVehicleId(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                <option value="">Optional...</option>
                {(allVehiclesQuery.data?.items ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.vehicle_code} ({v.status})
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setNewDisruptionModalOpen(false)}
              className="rounded bg-surface-container px-4 py-2 text-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createDisruptionMutation.isPending}
              className="rounded bg-primary-fixed px-4 py-2 font-display font-bold text-on-primary-fixed"
            >
              Create Disruption
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}


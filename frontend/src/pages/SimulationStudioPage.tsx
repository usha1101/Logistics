import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pause, Play, Plus, RotateCcw, Square, Truck, Zap } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  BengaluruNetworkMap,
  type MapEdgeSegment,
  type MapNodePoint,
  type MapVehicleMarker,
} from '@/components/maps/BengaluruNetworkMap'
import { KpiCard } from '@/components/ui/KpiCard'
import { EmptyState, ErrorState, LoadingState, UnavailableNotice } from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ACTION_PERMISSIONS, hasAnyRole } from '@/config/permissions'
import { ROUTES } from '@/config/routes'
import { formatDateTimeShort, getApiErrorMessage } from '@/lib/formatters'
import { disruptionService } from '@/services/disruption.service'
import { fleetService } from '@/services/fleet.service'
import { networkService } from '@/services/network.service'
import { simulationService } from '@/services/simulation.service'
import { warehouseService } from '@/services/warehouse.service'
import { useAuth } from '@/stores/auth-context'
import type { SimulationVehicleRead, SimulationWsMessage } from '@/types/simulation'

export function SimulationStudioPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const canControlSim = hasAnyRole(user?.role, ACTION_PERMISSIONS.SIMULATION_CONTROL)
  const canInjectDisruption = hasAnyRole(user?.role, ACTION_PERMISSIONS.DISRUPTION_OPERATE)

  const [selectedSimId, setSelectedSimId] = useState<string | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [livePositions, setLivePositions] = useState<Record<string, { lat: number; lon: number; progress: number; speed: number }>>({})
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const [assignVehicleId, setAssignVehicleId] = useState('')
  const [originNodeId, setOriginNodeId] = useState('')
  const [destNodeId, setDestNodeId] = useState('')

  const [targetVehicleForFault, setTargetVehicleForFault] = useState('')
  const [targetEdgeForCongestion, setTargetEdgeForCongestion] = useState('')
  const [targetWhForStoppage, setTargetWhForStoppage] = useState('')

  const simsQuery = useQuery({
    queryKey: ['simulations', 'studio'],
    queryFn: () => simulationService.listSimulations({ limit: 20 }),
    refetchInterval: 10_000,
  })

  const nodesQuery = useQuery({
    queryKey: ['network', 'nodes', 'sim-studio'],
    queryFn: () => networkService.listNodes({ is_active: true, limit: 100 }),
  })

  const edgesQuery = useQuery({
    queryKey: ['network', 'edges', 'sim-studio'],
    queryFn: () => networkService.listEdges({ is_active: true, limit: 100 }),
  })

  const fleetQuery = useQuery({
    queryKey: ['fleet', 'vehicles', 'sim-studio'],
    queryFn: () => fleetService.listVehicles({ is_active: true, limit: 50 }),
  })

  const warehousesQuery = useQuery({
    queryKey: ['warehouses', 'sim-studio'],
    queryFn: () => warehouseService.listWarehouses({ limit: 50 }),
  })

  const activeSim = useMemo(() => {
    const items = simsQuery.data?.items ?? []
    return (
      items.find((s) => s.id === selectedSimId) ??
      items.find((s) => s.status === 'RUNNING') ??
      items[0] ??
      null
    )
  }, [simsQuery.data, selectedSimId])

  const summaryQuery = useQuery({
    queryKey: ['simulations', 'summary', activeSim?.id],
    queryFn: () => simulationService.getSummary(activeSim!.id),
    enabled: Boolean(activeSim?.id),
    refetchInterval: 5000,
  })

  const simVehiclesQuery = useQuery({
    queryKey: ['simulations', 'vehicles', activeSim?.id],
    queryFn: () => simulationService.listVehicles(activeSim!.id),
    enabled: Boolean(activeSim?.id),
    refetchInterval: 5000,
  })

  const simEventsQuery = useQuery({
    queryKey: ['simulations', 'events', activeSim?.id],
    queryFn: () => simulationService.listEvents(activeSim!.id, { limit: 20 }),
    enabled: Boolean(activeSim?.id),
    refetchInterval: 5000,
  })

  const simDisruptionsQuery = useQuery({
    queryKey: ['disruptions', 'sim-studio', activeSim?.id],
    queryFn: () =>
      disruptionService.listDisruptions({
        simulation_id: activeSim?.id,
        page: 1,
        page_size: 10,
      }),
    enabled: Boolean(activeSim?.id),
  })

  // Live WebSocket subscription (/simulations/{id}/ws)
  useEffect(() => {
    if (!activeSim?.id) {
      setWsConnected(false)
      return
    }
    const wsUrl = simulationService.getWebSocketUrl(activeSim.id)
    const ws = new WebSocket(wsUrl)
    let pingTimer: number | null = null

    ws.onopen = () => {
      setWsConnected(true)
      pingTimer = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 15_000)
    }

    ws.onmessage = (evt) => {
      if (evt.data === 'pong') return
      try {
        const msg = JSON.parse(evt.data) as SimulationWsMessage
        if (
          msg.event === 'VEHICLE_POSITION_UPDATED' &&
          msg.vehicle_id &&
          typeof msg.latitude === 'number' &&
          typeof msg.longitude === 'number'
        ) {
          setLivePositions((prev) => ({
            ...prev,
            [msg.vehicle_id!]: {
              lat: msg.latitude!,
              lon: msg.longitude!,
              progress: msg.progress_percentage ?? prev[msg.vehicle_id!]?.progress ?? 0,
              speed: msg.speed_kmph ?? prev[msg.vehicle_id!]?.speed ?? 45,
            },
          }))
        } else {
          void queryClient.invalidateQueries({ queryKey: ['simulations'] })
        }
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => setWsConnected(false)
    ws.onerror = () => setWsConnected(false)

    return () => {
      if (pingTimer) window.clearInterval(pingTimer)
      ws.close()
    }
  }, [activeSim?.id, queryClient])

  const createSimMutation = useMutation({
    mutationFn: () =>
      simulationService.createSimulation({
        name: `Bengaluru Digital Twin #${(simsQuery.data?.total ?? 0) + 1}`,
        seed: 42,
        simulation_speed_multiplier: 1,
      }),
    onSuccess: (created) => {
      setActionErr(null)
      setActionMsg(`Created simulation run "${created.name}".`)
      setSelectedSimId(created.id)
      setLivePositions({})
      void queryClient.invalidateQueries({ queryKey: ['simulations'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const lifecycleMutation = useMutation({
    mutationFn: async (action: 'start' | 'pause' | 'resume' | 'stop' | 'reset') => {
      if (!activeSim) throw new Error('No simulation selected')
      if (action === 'start') return simulationService.start(activeSim.id)
      if (action === 'pause') return simulationService.pause(activeSim.id)
      if (action === 'resume') return simulationService.resume(activeSim.id)
      if (action === 'stop') return simulationService.stop(activeSim.id)
      return simulationService.reset(activeSim.id)
    },
    onSuccess: (res) => {
      setActionErr(null)
      setActionMsg(`Simulation state: ${res.status}`)
      void queryClient.invalidateQueries({ queryKey: ['simulations'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const speedMutation = useMutation({
    mutationFn: (speed: number) => simulationService.updateSpeed(activeSim!.id, speed),
    onSuccess: (res) => {
      setActionErr(null)
      setActionMsg(`Updated playback speed to ${res.simulation_speed_multiplier}x.`)
      void queryClient.invalidateQueries({ queryKey: ['simulations'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const assignVehicleMutation = useMutation({
    mutationFn: () =>
      simulationService.assignVehicle(activeSim!.id, {
        vehicle_id: assignVehicleId,
        origin_node_id: originNodeId,
        destination_node_id: destNodeId,
      }),
    onSuccess: (vs) => {
      setActionErr(null)
      setActionMsg(`Assigned ${vs.vehicle_code ?? vs.vehicle_id} to simulation corridor.`)
      void queryClient.invalidateQueries({ queryKey: ['simulations'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const injectDisruptionMutation = useMutation({
    mutationFn: async (type: 'VEHICLE_BREAKDOWN' | 'TRAFFIC_CONGESTION' | 'WAREHOUSE_SHUTDOWN' | 'DEMAND_SURGE') => {
      if (type === 'VEHICLE_BREAKDOWN') {
        const vid = targetVehicleForFault || fleetQuery.data?.items[0]?.id
        return disruptionService.createDisruption({
          disruption_type: 'VEHICLE_BREAKDOWN',
          title: 'Simulated Vehicle Breakdown Fault',
          severity: 'CRITICAL',
          simulation_id: activeSim?.id ?? null,
          affected_vehicle_id: vid,
        })
      }
      if (type === 'TRAFFIC_CONGESTION') {
        const eid = targetEdgeForCongestion || edgesQuery.data?.items[0]?.id
        return disruptionService.createDisruption({
          disruption_type: 'TRAFFIC_CONGESTION',
          title: 'Simulated Corridor Congestion',
          severity: 'HIGH',
          simulation_id: activeSim?.id ?? null,
          affected_network_edge_id: eid,
        })
      }
      if (type === 'WAREHOUSE_SHUTDOWN') {
        const wid = targetWhForStoppage || warehousesQuery.data?.items[0]?.id
        return disruptionService.createDisruption({
          disruption_type: 'WAREHOUSE_SHUTDOWN',
          title: 'Simulated Warehouse Operational Stoppage',
          severity: 'CRITICAL',
          simulation_id: activeSim?.id ?? null,
          affected_warehouse_id: wid,
        })
      }
      return disruptionService.createDisruption({
        disruption_type: 'DEMAND_SURGE',
        title: 'Simulated Demand Surge Spike',
        severity: 'MEDIUM',
        simulation_id: activeSim?.id ?? null,
      })
    },
    onSuccess: (created) => {
      setActionErr(null)
      setActionMsg(`Injected ${created.disruption_code} (${created.disruption_type}). Inspect recovery under Optimization & Recovery.`)
      void queryClient.invalidateQueries({ queryKey: ['disruptions'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const nodesList = nodesQuery.data?.items ?? []
  const edgesList = edgesQuery.data?.items ?? []

  const { mapNodes, mapEdges } = useMemo(() => {
    const nodeCoordMap = new Map<string, [number, number]>()
    const nodes: MapNodePoint[] = nodesList.map((n) => {
      nodeCoordMap.set(n.id, [n.latitude, n.longitude])
      return {
        id: n.id,
        name: n.name,
        nodeType: n.node_type,
        latitude: n.latitude,
        longitude: n.longitude,
      }
    })
    const edges: MapEdgeSegment[] = []
    for (const e of edgesList) {
      const from = nodeCoordMap.get(e.source_node_id)
      const to = nodeCoordMap.get(e.target_node_id)
      if (from && to) {
        edges.push({
          id: e.id,
          from,
          to,
          label: `${e.distance_km} km • ${e.estimated_travel_minutes}m`,
        })
      }
    }
    return { mapNodes: nodes, mapEdges: edges }
  }, [nodesList, edgesList])

  const simVehicles: SimulationVehicleRead[] = simVehiclesQuery.data ?? []

  const mapVehicles = useMemo<MapVehicleMarker[]>(() => {
    return simVehicles.map((sv) => {
      const live = livePositions[sv.vehicle_id]
      return {
        id: sv.vehicle_id,
        code: sv.vehicle_code ?? sv.vehicle_id.slice(0, 8),
        status: sv.status,
        latitude: live?.lat ?? sv.current_latitude,
        longitude: live?.lon ?? sv.current_longitude,
        speedKmph: live?.speed ?? sv.current_speed_kmph,
      }
    })
  }, [simVehicles, livePositions])

  if (simsQuery.isLoading) {
    return <LoadingState message="Loading simulation twin studio..." />
  }

  if (simsQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(simsQuery.error)}
        onRetry={() => void simsQuery.refetch()}
      />
    )
  }

  const simSummary = summaryQuery.data

  return (
    <div className="space-y-6">
      {/* Runtime Selector & WebSocket Status Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={activeSim?.id ?? ''}
            onChange={(e) => {
              setSelectedSimId(e.target.value)
              setLivePositions({})
            }}
            className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 text-xs font-semibold text-primary"
          >
            {(simsQuery.data?.items ?? []).length === 0 && <option value="">No simulations found</option>}
            {(simsQuery.data?.items ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.status})
              </option>
            ))}
          </select>

          {activeSim && <StatusBadge value={activeSim.status} pulse={activeSim.status === 'RUNNING'} />}

          <span className="font-telemetry text-xs text-secondary">
            WS Stream:{' '}
            <strong className={wsConnected ? 'text-lime' : 'text-outline'}>
              {wsConnected ? 'CONNECTED' : 'DISCONNECTED'}
            </strong>
          </span>
        </div>

        {canControlSim && (
          <button
            type="button"
            disabled={createSimMutation.isPending}
            onClick={() => createSimMutation.mutate()}
            className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3 py-1.5 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
          >
            <Plus className="h-3.5 w-3.5" />
            New Simulation
          </button>
        )}
      </div>

      {/* 3 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          label="Simulated Vehicles"
          value={simSummary?.total_vehicles ?? simVehicles.length}
          sublabel={`${simSummary?.en_route_vehicles ?? 0} en route • ${simSummary?.arrived_vehicles ?? 0} arrived`}
          icon={<Truck className="h-4 w-4" />}
        />
        <KpiCard
          label="Average Route Progress"
          value={`${(simSummary?.average_progress_percentage ?? 0).toFixed(1)}%`}
          sublabel={`Speed multiplier: ${activeSim?.simulation_speed_multiplier ?? 1}x`}
          accent="lime"
        />
        <KpiCard
          label="Events & Disruptions"
          value={simSummary?.total_events ?? simEventsQuery.data?.total ?? 0}
          sublabel={`${simSummary?.total_telemetry_points ?? 0} telemetry points • ${simDisruptionsQuery.data?.total ?? 0} disruptions`}
          accent="info"
        />
      </section>

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

      {/* Main Split: Twin Canvas + Controls (8 cols) & Disruption Injection (4 cols) */}
      <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="xl:col-span-8 space-y-4">
          {/* Playback Control Bar */}
          {activeSim ? (
            <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                {canControlSim ? (
                  <>
                    <button
                      type="button"
                      disabled={
                        lifecycleMutation.isPending ||
                        !['CREATED', 'PAUSED'].includes(activeSim.status)
                      }
                      onClick={() =>
                        lifecycleMutation.mutate(activeSim.status === 'PAUSED' ? 'resume' : 'start')
                      }
                      className="inline-flex items-center gap-1 rounded bg-primary-fixed px-3 py-1.5 font-display text-xs font-bold text-on-primary-fixed disabled:opacity-40"
                    >
                      <Play className="h-3.5 w-3.5" />
                      {activeSim.status === 'PAUSED' ? 'Resume' : 'Start'}
                    </button>
                    <button
                      type="button"
                      disabled={lifecycleMutation.isPending || activeSim.status !== 'RUNNING'}
                      onClick={() => lifecycleMutation.mutate('pause')}
                      className="inline-flex items-center gap-1 rounded bg-surface-container px-3 py-1.5 font-display text-xs font-semibold text-primary disabled:opacity-40"
                    >
                      <Pause className="h-3.5 w-3.5" />
                      Pause
                    </button>
                    <button
                      type="button"
                      disabled={
                        lifecycleMutation.isPending ||
                        !['RUNNING', 'PAUSED'].includes(activeSim.status)
                      }
                      onClick={() => lifecycleMutation.mutate('stop')}
                      className="inline-flex items-center gap-1 rounded bg-surface-container px-3 py-1.5 font-display text-xs font-semibold text-error disabled:opacity-40"
                    >
                      <Square className="h-3.5 w-3.5" />
                      Stop
                    </button>
                    <button
                      type="button"
                      disabled={
                        lifecycleMutation.isPending ||
                        !['STOPPED', 'COMPLETED'].includes(activeSim.status)
                      }
                      onClick={() => lifecycleMutation.mutate('reset')}
                      className="inline-flex items-center gap-1 rounded bg-surface-container px-3 py-1.5 font-display text-xs font-semibold text-secondary hover:text-primary disabled:opacity-40"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      Reset
                    </button>
                  </>
                ) : (
                  <span className="text-xs text-outline">
                    Simulation controls require ADMIN or OPERATIONS_MANAGER role.
                  </span>
                )}
              </div>

              {canControlSim && (
                <div className="flex items-center gap-1 rounded bg-surface-container-lowest p-1 font-telemetry text-xs">
                  {[1, 2, 5, 10].map((mult) => (
                    <button
                      key={mult}
                      type="button"
                      onClick={() => speedMutation.mutate(mult)}
                      className={`rounded px-2.5 py-1 font-bold ${
                        activeSim.simulation_speed_multiplier === mult
                          ? 'bg-primary-fixed text-on-primary-fixed'
                          : 'text-secondary hover:text-primary'
                      }`}
                    >
                      {mult}x
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <EmptyState
              title="No simulation instances found"
              description="Create a new digital twin run to simulate vehicle routes across Bengaluru."
            />
          )}

          {/* Twin Map */}
          <BengaluruNetworkMap
            nodes={mapNodes}
            edges={mapEdges}
            vehicles={mapVehicles}
            heightClass="h-[430px]"
          />

          {/* Assign Vehicle to Simulation */}
          {activeSim && canControlSim && (
            <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-2">
              <div className="font-display text-xs font-bold uppercase tracking-wider text-outline">
                Dispatch Vehicle Inside Twin
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-4 text-xs">
                <select
                  value={assignVehicleId}
                  onChange={(e) => setAssignVehicleId(e.target.value)}
                  className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-2 text-primary"
                >
                  <option value="">Select Vehicle...</option>
                  {(fleetQuery.data?.items ?? [])
                    .filter(
                      (v) =>
                        !['BREAKDOWN', 'MAINTENANCE', 'OFFLINE'].includes(v.status) &&
                        !simVehicles.some((sv) => sv.vehicle_id === v.id),
                    )
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.vehicle_code} ({v.status})
                      </option>
                    ))}
                </select>
                <select
                  value={originNodeId}
                  onChange={(e) => setOriginNodeId(e.target.value)}
                  className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-2 text-primary"
                >
                  <option value="">Origin Node...</option>
                  {nodesList.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name}
                    </option>
                  ))}
                </select>
                <select
                  value={destNodeId}
                  onChange={(e) => setDestNodeId(e.target.value)}
                  className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-2 text-primary"
                >
                  <option value="">Destination Node...</option>
                  {nodesList.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={
                    !assignVehicleId ||
                    !originNodeId ||
                    !destNodeId ||
                    assignVehicleMutation.isPending
                  }
                  onClick={() => assignVehicleMutation.mutate()}
                  className="rounded bg-primary-fixed px-3 py-2 font-display font-bold text-on-primary-fixed disabled:opacity-40"
                >
                  Assign Route
                </button>
              </div>
            </div>
          )}

          {/* Simulation Event Stream */}
          <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-2">
            <h3 className="font-display text-sm font-bold text-primary">
              Simulation Event Audit ({simEventsQuery.data?.total ?? 0})
            </h3>
            <div className="max-h-48 space-y-1.5 overflow-y-auto font-telemetry text-xs">
              {(simEventsQuery.data?.items ?? []).map((ev) => (
                <div
                  key={ev.id}
                  className="flex items-center justify-between rounded bg-surface-container px-3 py-1.5"
                >
                  <span className="text-lime font-semibold">{ev.event_type}</span>
                  <span className="text-secondary">
                    {formatDateTimeShort(ev.created_at ?? ev.simulated_timestamp)}
                  </span>
                </div>
              ))}
              {(simEventsQuery.data?.items ?? []).length === 0 && (
                <p className="text-outline">No simulation events recorded yet.</p>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Disruption Injection Engine */}
        <div className="xl:col-span-4 space-y-4">
          <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-sm font-bold text-primary">
                  Disruption Injection Engine
                </h2>
                <p className="text-xs text-secondary">
                  Creates real records via `POST /api/v1/disruptions`
                </p>
              </div>
              <Zap className="h-4 w-4 text-lime" />
            </div>

            {canInjectDisruption ? (
              <div className="space-y-3 text-xs">
                <div className="rounded bg-surface-container p-3 space-y-2">
                  <div className="flex justify-between font-bold text-primary">
                    <span>Vehicle Breakdown</span>
                    <StatusBadge value="CRITICAL" />
                  </div>
                  <select
                    value={targetVehicleForFault}
                    onChange={(e) => setTargetVehicleForFault(e.target.value)}
                    className="w-full rounded border border-surface-container-highest bg-surface-container-lowest px-2.5 py-1.5 text-primary"
                  >
                    {(fleetQuery.data?.items ?? []).map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.vehicle_code} ({v.status})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={injectDisruptionMutation.isPending}
                    onClick={() => injectDisruptionMutation.mutate('VEHICLE_BREAKDOWN')}
                    className="w-full rounded bg-[#EF4444]/20 py-1.5 font-display font-bold text-[#F87171] hover:bg-[#EF4444]/30"
                  >
                    Inject Breakdown Disruption
                  </button>
                </div>

                <div className="rounded bg-surface-container p-3 space-y-2">
                  <div className="flex justify-between font-bold text-primary">
                    <span>Traffic Congestion</span>
                    <StatusBadge value="HIGH" />
                  </div>
                  <select
                    value={targetEdgeForCongestion}
                    onChange={(e) => setTargetEdgeForCongestion(e.target.value)}
                    className="w-full rounded border border-surface-container-highest bg-surface-container-lowest px-2.5 py-1.5 text-primary"
                  >
                    {edgesList.slice(0, 20).map((ed) => (
                      <option key={ed.id} value={ed.id}>
                        Edge {ed.id.slice(0, 8)} ({ed.distance_km} km, {ed.road_type ?? 'Road'})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={injectDisruptionMutation.isPending}
                    onClick={() => injectDisruptionMutation.mutate('TRAFFIC_CONGESTION')}
                    className="w-full rounded bg-[#F59E0B]/20 py-1.5 font-display font-bold text-[#FBBF24] hover:bg-[#F59E0B]/30"
                  >
                    Inject Corridor Bottleneck
                  </button>
                </div>

                <div className="rounded bg-surface-container p-3 space-y-2">
                  <div className="flex justify-between font-bold text-primary">
                    <span>Warehouse Shutdown</span>
                    <StatusBadge value="CRITICAL" />
                  </div>
                  <select
                    value={targetWhForStoppage}
                    onChange={(e) => setTargetWhForStoppage(e.target.value)}
                    className="w-full rounded border border-surface-container-highest bg-surface-container-lowest px-2.5 py-1.5 text-primary"
                  >
                    {(warehousesQuery.data?.items ?? []).map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.warehouse_code} ({w.status})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={injectDisruptionMutation.isPending}
                    onClick={() => injectDisruptionMutation.mutate('WAREHOUSE_SHUTDOWN')}
                    className="w-full rounded bg-surface-container-highest py-1.5 font-display font-bold text-primary hover:bg-surface-bright"
                  >
                    Inject Warehouse Stoppage
                  </button>
                </div>

                <div className="rounded bg-surface-container p-3 space-y-2">
                  <div className="flex justify-between font-bold text-primary">
                    <span>Demand Surge</span>
                    <StatusBadge value="MEDIUM" />
                  </div>
                  <button
                    type="button"
                    disabled={injectDisruptionMutation.isPending}
                    onClick={() => injectDisruptionMutation.mutate('DEMAND_SURGE')}
                    className="w-full rounded bg-primary-fixed/20 py-1.5 font-display font-bold text-lime hover:bg-primary-fixed/30"
                  >
                    Inject Demand Surge
                  </button>
                </div>
              </div>
            ) : (
              <UnavailableNotice
                title="Disruption Injection Restricted"
                description="Injecting disruptions requires ADMIN, OPERATIONS_MANAGER, FLEET_MANAGER, or WAREHOUSE_MANAGER permissions."
              />
            )}
          </div>

          {/* Linked Disruptions List */}
          <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-sm font-bold text-primary">
                Simulation Disruptions
              </h3>
              <Link to={ROUTES.RECOVERY} className="font-telemetry text-xs text-lime hover:underline">
                Open Recovery -&gt;
              </Link>
            </div>
            <div className="space-y-2 text-xs">
              {(simDisruptionsQuery.data?.items ?? []).map((d) => (
                <div key={d.id} className="rounded bg-surface-container p-2.5 space-y-1">
                  <div className="flex justify-between">
                    <span className="font-telemetry font-bold text-lime">{d.disruption_code}</span>
                    <StatusBadge value={d.status} />
                  </div>
                  <div className="text-primary">{d.title}</div>
                </div>
              ))}
              {(simDisruptionsQuery.data?.items ?? []).length === 0 && (
                <p className="text-outline">No disruptions linked to this simulation run.</p>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}


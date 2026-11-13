import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  Cpu,
  Network,
  Package,
  ShieldCheck,
  Truck,
  Warehouse,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  BengaluruNetworkMap,
  type MapEdgeSegment,
  type MapNodePoint,
  type MapVehicleMarker,
} from '@/components/maps/BengaluruNetworkMap'
import { KpiCard } from '@/components/ui/KpiCard'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ROUTES } from '@/config/routes'
import {
  formatDateTimeShort,
  formatNumber,
  formatPercent,
  getApiErrorMessage,
} from '@/lib/formatters'
import { agentService } from '@/services/agent.service'
import { analyticsService } from '@/services/analytics.service'
import { dashboardService } from '@/services/dashboard.service'
import { disruptionService } from '@/services/disruption.service'
import { fleetService } from '@/services/fleet.service'
import { networkService } from '@/services/network.service'

const FLEET_CHART_COLORS: Record<string, string> = {
  IN_TRANSIT: '#3B82F6',
  AVAILABLE: '#22C55E',
  MAINTENANCE: '#F97316',
  BREAKDOWN: '#EF4444',
  IDLE: '#9E9FA6',
  OFFLINE: '#4B5563',
}

export function CommandCentrePage() {
  const [mapFilter, setMapFilter] = useState<'ALL' | 'IN_TRANSIT' | 'AVAILABLE' | 'ALERTS'>('ALL')
  const [feedFilter, setFeedFilter] = useState<'ALL' | 'DISRUPTIONS' | 'AGENTS' | 'RESOLVED'>('ALL')
  const [showEdges, setShowEdges] = useState(true)
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null)

  const summaryQuery = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => dashboardService.getSummary(),
    refetchInterval: 15_000,
  })

  const geoJsonQuery = useQuery({
    queryKey: ['network', 'geojson'],
    queryFn: () => networkService.getGeoJson({ only_active: true }),
  })

  const vehiclesQuery = useQuery({
    queryKey: ['fleet', 'vehicles', 'command-centre'],
    queryFn: () => fleetService.listVehicles({ limit: 50 }),
    refetchInterval: 10_000,
  })

  const disruptionsQuery = useQuery({
    queryKey: ['disruptions', 'command-centre'],
    queryFn: () => disruptionService.listDisruptions({ page: 1, page_size: 8 }),
    refetchInterval: 15_000,
  })

  const agentRunsQuery = useQuery({
    queryKey: ['agents', 'runs', 'command-centre'],
    queryFn: () => agentService.listRuns({ page: 1, page_size: 5 }),
    refetchInterval: 15_000,
  })

  const orderTrendsQuery = useQuery({
    queryKey: ['analytics', 'orders-trends'],
    queryFn: () => analyticsService.getOrderTrends({ grouping: 'DAY', include_simulations: true }),
  })

  const { mapNodes, mapEdges } = useMemo(() => {
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
          subtitle: f.properties.region ? String(f.properties.region) : undefined,
        })
      }
    }

    if (showEdges) {
      for (const f of features) {
        if (f.geometry.type === 'LineString') {
          const coords = f.geometry.coordinates as [number, number][]
          if (coords.length >= 2) {
            edges.push({
              id: f.id,
              from: [coords[0][1], coords[0][0]],
              to: [coords[coords.length - 1][1], coords[coords.length - 1][0]],
              label: `${String(f.properties.road_type ?? 'Route')} (${String(f.properties.distance_km ?? '?')} km)`,
            })
          }
        }
      }
    }
    return { mapNodes: nodes, mapEdges: edges }
  }, [geoJsonQuery.data, showEdges])

  const vehicles = vehiclesQuery.data?.items ?? []

  const filteredVehicles = useMemo<MapVehicleMarker[]>(() => {
    return vehicles
      .filter((v) => v.current_latitude !== null && v.current_longitude !== null)
      .filter((v) => {
        if (mapFilter === 'IN_TRANSIT') return v.status === 'IN_TRANSIT'
        if (mapFilter === 'AVAILABLE') return v.status === 'AVAILABLE'
        if (mapFilter === 'ALERTS') return v.status === 'BREAKDOWN' || v.status === 'MAINTENANCE'
        return true
      })
      .map((v) => ({
        id: v.id,
        code: v.vehicle_code,
        status: v.status,
        latitude: v.current_latitude as number,
        longitude: v.current_longitude as number,
        speedKmph: v.current_speed_kmph,
        selected: v.id === selectedVehicleId,
      }))
  }, [vehicles, mapFilter, selectedVehicleId])

  const selectedVehicle = useMemo(
    () =>
      vehicles.find((v) => v.id === selectedVehicleId) ??
      vehicles.find((v) => v.status === 'BREAKDOWN') ??
      vehicles[0] ??
      null,
    [vehicles, selectedVehicleId],
  )

  const fleetStatusBreakdown = useMemo(() => {
    const counts = new Map<string, number>()
    for (const v of vehicles) {
      counts.set(v.status, (counts.get(v.status) ?? 0) + 1)
    }
    return Array.from(counts.entries()).map(([status, value]) => ({
      name: status.replace(/_/g, ' '),
      status,
      value,
      color: FLEET_CHART_COLORS[status] ?? '#9E9FA6',
    }))
  }, [vehicles])

  if (summaryQuery.isLoading) {
    return <LoadingState message="Loading Command Centre unified KPIs..." />
  }

  if (summaryQuery.isError) {
    return (
      <ErrorState
        title="Command Centre Unavailable"
        message={getApiErrorMessage(summaryQuery.error)}
        onRetry={() => void summaryQuery.refetch()}
      />
    )
  }

  const summary = summaryQuery.data!
  const recoverySummary = (summary.recovery_summary ?? {}) as Record<string, number | undefined>
  const agentSummary = (summary.agent_summary ?? {}) as Record<string, number | undefined>

  const disruptions = disruptionsQuery.data?.items ?? []
  const agentRuns = agentRunsQuery.data?.items ?? []

  return (
    <div className="space-y-6">
      {/* Top 6 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          label="Warehouses"
          value={summary.network.total_warehouses}
          sublabel={`${summary.network.operational_warehouses ?? 0} operational`}
          icon={<Warehouse className="h-4 w-4" />}
        />
        <KpiCard
          label="Network Scale"
          value={`${summary.network.total_customers} Customers`}
          sublabel={`${summary.network.total_network_connections} active corridors`}
          icon={<Network className="h-4 w-4" />}
        />
        <KpiCard
          label="Fleet Assets"
          value={summary.operations.total_vehicles ?? 0}
          sublabel={`${summary.operations.in_transit_vehicles ?? 0} in transit`}
          accent="info"
          icon={<Truck className="h-4 w-4" />}
        />
        <KpiCard
          label="Active Orders"
          value={summary.operations.total_orders ?? 0}
          sublabel={`${summary.operations.pending_orders ?? 0} pending • ${summary.operations.delayed_orders ?? 0} overdue`}
          accent={(summary.operations.delayed_orders ?? 0) > 0 ? 'warn' : 'default'}
          icon={<Package className="h-4 w-4" />}
        />
        <KpiCard
          label="Disruptions"
          value={summary.disruptions?.active_disruptions ?? 0}
          sublabel={`${summary.disruptions?.critical_disruptions ?? 0} critical alerts`}
          accent={(summary.disruptions?.active_disruptions ?? 0) > 0 ? 'danger' : 'success'}
          icon={<AlertTriangle className="h-4 w-4" />}
        />
        <KpiCard
          label="Delivery SLA"
          value={formatPercent(summary.performance.on_time_delivery_rate)}
          sublabel={`Fleet load util: ${formatPercent(summary.performance.fleet_utilization)}`}
          accent="lime"
          icon={<Activity className="h-4 w-4" />}
        />
      </section>

      {/* Main Two-Column Split: Map (8 cols) + Intelligence Feed (4 cols) */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 flex flex-col gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              {(
                [
                  ['ALL', `All (${vehicles.length})`],
                  ['IN_TRANSIT', `In Transit (${vehicles.filter((v) => v.status === 'IN_TRANSIT').length})`],
                  ['AVAILABLE', `Available (${vehicles.filter((v) => v.status === 'AVAILABLE').length})`],
                  [
                    'ALERTS',
                    `Alerts (${vehicles.filter((v) => v.status === 'BREAKDOWN' || v.status === 'MAINTENANCE').length})`,
                  ],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setMapFilter(key)}
                  className={`rounded px-2.5 py-1 font-telemetry text-xs font-semibold transition-colors ${
                    mapFilter === key
                      ? 'bg-primary-fixed text-on-primary-fixed'
                      : 'bg-surface-container text-secondary hover:text-primary'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => setShowEdges((prev) => !prev)}
              className={`rounded border px-2.5 py-1 font-telemetry text-xs transition-colors ${
                showEdges
                  ? 'border-primary-fixed/40 bg-primary-fixed/10 text-primary-fixed'
                  : 'border-surface-container-highest bg-surface-container text-secondary'
              }`}
            >
              {showEdges ? 'Corridors: Visible' : 'Corridors: Hidden'}
            </button>
          </div>

          <div className="relative">
            <BengaluruNetworkMap
              nodes={mapNodes}
              edges={mapEdges}
              vehicles={filteredVehicles}
              heightClass="h-[440px]"
              onSelectVehicle={(id) => setSelectedVehicleId(id)}
            />

            {selectedVehicle && (
              <div className="mt-3 rounded-md border border-surface-container-highest bg-surface-container-lowest/90 p-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-display text-sm font-bold text-primary">
                      {selectedVehicle.vehicle_code}
                    </span>
                    <StatusBadge value={selectedVehicle.status} />
                  </div>
                  <p className="mt-0.5 font-telemetry text-xs text-secondary">
                    {selectedVehicle.manufacturer ?? 'Fleet Unit'} {selectedVehicle.model ?? ''} •{' '}
                    Load {formatNumber(selectedVehicle.current_load_kg)} /{' '}
                    {formatNumber(selectedVehicle.capacity_kg)} kg
                  </p>
                </div>
                <div className="flex items-center gap-3 font-telemetry text-xs text-on-surface-variant">
                  <span>
                    Speed: {selectedVehicle.current_speed_kmph?.toFixed(0) ?? '0'} km/h
                  </span>
                  <Link
                    to={ROUTES.FLEET}
                    className="rounded bg-surface-container-high px-2.5 py-1 text-primary-fixed hover:bg-surface-bright"
                  >
                    Inspect in Fleet
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Real Disruptions & AI Agent Feed */}
        <div className="lg:col-span-4 flex flex-col rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          <div className="flex items-center justify-between border-b border-surface-container-highest pb-3">
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-lime" />
              <div>
                <h2 className="font-display text-sm font-bold text-primary">
                  Intelligence &amp; Incident Feed
                </h2>
                <p className="font-telemetry text-[10px] uppercase text-outline">
                  Live Disruptions &amp; AI Runs
                </p>
              </div>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap gap-1 rounded bg-surface-container p-1 font-telemetry text-[11px]">
            {(
              [
                ['ALL', 'All'],
                ['DISRUPTIONS', 'Disruptions'],
                ['AGENTS', 'Agent Runs'],
                ['RESOLVED', 'Resolved'],
              ] as const
            ).map(([k, lbl]) => (
              <button
                key={k}
                type="button"
                onClick={() => setFeedFilter(k)}
                className={`flex-1 rounded px-2 py-1 transition-colors ${
                  feedFilter === k
                    ? 'bg-surface-container-highest text-primary font-bold'
                    : 'text-secondary hover:text-primary'
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>

          <div className="mt-3 flex-1 space-y-2.5 overflow-y-auto max-h-[450px] pr-1">
            {(feedFilter === 'ALL' || feedFilter === 'DISRUPTIONS' || feedFilter === 'RESOLVED') &&
              disruptions
                .filter((d) => (feedFilter === 'RESOLVED' ? d.status === 'RESOLVED' : true))
                .map((d) => (
                  <div
                    key={d.id}
                    className="rounded-md border border-surface-container-highest bg-surface-container p-3 space-y-1.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-telemetry text-[11px] font-bold text-primary-fixed">
                        {d.disruption_code}
                      </span>
                      <StatusBadge value={d.severity} />
                    </div>
                    <p className="text-xs font-semibold text-primary">{d.title}</p>
                    <div className="flex items-center justify-between text-[11px] text-secondary">
                      <StatusBadge value={d.status} />
                      <span>{formatDateTimeShort(d.created_at)}</span>
                    </div>
                  </div>
                ))}

            {(feedFilter === 'ALL' || feedFilter === 'AGENTS') &&
              agentRuns.map((run) => (
                <div
                  key={run.id}
                  className="rounded-md border border-outline-variant/40 bg-surface-container-lowest p-3 space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-telemetry text-[11px] font-bold text-on-surface">
                      AI RUN • {run.primary_provider.toUpperCase()}
                    </span>
                    <StatusBadge value={run.status} />
                  </div>
                  <p className="text-xs text-secondary">
                    {run.recommendations.length} validated recommendations across{' '}
                    {run.executions.length} agents
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-outline">
                    <span>
                      {run.execution_duration_ms
                        ? `${Math.round(run.execution_duration_ms)} ms`
                        : 'Pending'}
                    </span>
                    <Link to={ROUTES.AGENTS} className="text-lime hover:underline">
                      Open Run
                    </Link>
                  </div>
                </div>
              ))}

            {disruptions.length === 0 && agentRuns.length === 0 && (
              <EmptyState
                title="No incidents or AI runs recorded"
                description="All corridors are currently clear. Trigger or create a disruption in Simulation Studio or Optimization & Recovery."
              />
            )}
          </div>
        </div>
      </section>

      {/* Bottom 3 Analytics Modules */}
      <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {/* Module A: Order Trend Recharts Area Chart */}
        <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 flex flex-col justify-between">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <span className="font-display text-[10px] font-bold uppercase tracking-wider text-outline">
                Order Volume Trend
              </span>
              <h3 className="font-display text-sm font-bold text-primary">
                Daily Consignments (/analytics/orders/trends)
              </h3>
            </div>
          </div>

          <div className="h-40 w-full">
            {orderTrendsQuery.data && orderTrendsQuery.data.data_points.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={orderTrendsQuery.data.data_points}>
                  <defs>
                    <linearGradient id="cmdLimeFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#C6F432" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#C6F432" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="period" tick={{ fill: '#9E9FA6', fontSize: 10 }} />
                  <YAxis tick={{ fill: '#9E9FA6', fontSize: 10 }} width={30} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1c1b1c',
                      border: '1px solid #353436',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#C6F432"
                    strokeWidth={2}
                    fill="url(#cmdLimeFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-secondary">
                No historical order trend buckets available yet.
              </div>
            )}
          </div>
        </div>

        {/* Module B: Live Fleet Breakdown Donut */}
        <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 flex flex-col justify-between">
          <div className="mb-2 flex items-center justify-between">
            <div>
              <span className="font-display text-[10px] font-bold uppercase tracking-wider text-outline">
                Fleet Distribution
              </span>
              <h3 className="font-display text-sm font-bold text-primary">
                Live Status Allocation ({vehicles.length} Units)
              </h3>
            </div>
            <span className="font-telemetry text-xs text-lime font-semibold">
              {formatPercent(summary.performance.fleet_utilization)} Load
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="h-36 w-36 shrink-0">
              {fleetStatusBreakdown.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={fleetStatusBreakdown}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={36}
                      outerRadius={54}
                      paddingAngle={2}
                    >
                      {fleetStatusBreakdown.map((entry) => (
                        <Cell key={entry.status} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1c1b1c',
                        border: '1px solid #353436',
                        fontSize: '12px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-secondary">
                  Empty fleet
                </div>
              )}
            </div>
            <div className="flex-1 space-y-1.5 font-telemetry text-xs">
              {fleetStatusBreakdown.map((item) => (
                <div key={item.status} className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-secondary">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    {item.name}
                  </span>
                  <span className="font-bold text-primary">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Module C: Recovery & Simulation SLA */}
        <div className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 flex flex-col justify-between">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <span className="font-display text-[10px] font-bold uppercase tracking-wider text-outline">
                Recovery &amp; Orchestration
              </span>
              <h3 className="font-display text-sm font-bold text-primary">
                Backend SLA Summary
              </h3>
            </div>
            <ShieldCheck className="h-5 w-5 text-lime" />
          </div>

          <div className="grid grid-cols-2 gap-2.5 font-telemetry">
            <div className="rounded bg-surface-container p-2.5">
              <span className="text-[10px] uppercase text-secondary block">Recovery Plans</span>
              <span className="text-lg font-bold text-primary">
                {recoverySummary.total_recovery_plans ?? 0}
              </span>
            </div>
            <div className="rounded bg-surface-container p-2.5">
              <span className="text-[10px] uppercase text-secondary block">Executed Plans</span>
              <span className="text-lg font-bold text-lime">
                {recoverySummary.executed_plans ?? 0}
              </span>
            </div>
            <div className="rounded bg-surface-container p-2.5">
              <span className="text-[10px] uppercase text-secondary block">AI Runs</span>
              <span className="text-lg font-bold text-primary">
                {agentSummary.total_agent_runs ?? 0}
              </span>
            </div>
            <div className="rounded bg-surface-container p-2.5">
              <span className="text-[10px] uppercase text-secondary block">Success Rate</span>
              <span className="text-lg font-bold text-[#22C55E]">
                {formatPercent(recoverySummary.recovery_success_rate ?? null)}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}


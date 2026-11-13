import { useQuery } from '@tanstack/react-query'
import { Maximize2, Minimize2, Network, Route as RouteIcon, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  BengaluruNetworkMap,
  type MapEdgeSegment,
  type MapNodePoint,
  type MapVehicleMarker,
} from '@/components/maps/BengaluruNetworkMap'
import { KpiCard } from '@/components/ui/KpiCard'
import { ErrorState, LoadingState, UnavailableNotice } from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ACTION_PERMISSIONS, hasAnyRole } from '@/config/permissions'
import { formatNumber, getApiErrorMessage } from '@/lib/formatters'
import { fleetService } from '@/services/fleet.service'
import { networkService } from '@/services/network.service'
import { warehouseService } from '@/services/warehouse.service'
import { useAuth } from '@/stores/auth-context'
import type { NetworkWeightType } from '@/types/network'

export function NetworkOverviewPage() {
  const { user } = useAuth()
  const canViewFullState = hasAnyRole(user?.role, ACTION_PERMISSIONS.NETWORK_STATE)

  const [selectedRegion, setSelectedRegion] = useState<string>('ALL')
  const [showNodes, setShowNodes] = useState(true)
  const [showEdges, setShowEdges] = useState(true)
  const [showVehicles, setShowVehicles] = useState(true)
  const [expandedMap, setExpandedMap] = useState(false)
  const [drawerTab, setDrawerTab] = useState<'NODE' | 'PATH'>('NODE')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [originId, setOriginId] = useState<string>('')
  const [destId, setDestId] = useState<string>('')
  const [weightMode, setWeightMode] = useState<NetworkWeightType>('distance')

  const analyticsQuery = useQuery({
    queryKey: ['network', 'analytics'],
    queryFn: () => networkService.getAnalytics(true),
  })

  const graphQuery = useQuery({
    queryKey: ['network', 'graph'],
    queryFn: () => networkService.getGraph(true),
  })

  const validationQuery = useQuery({
    queryKey: ['network', 'validation'],
    queryFn: () => networkService.getValidation(),
  })

  const geoJsonQuery = useQuery({
    queryKey: ['network', 'geojson'],
    queryFn: () => networkService.getGeoJson({ only_active: true }),
  })

  const stateQuery = useQuery({
    queryKey: ['network', 'state'],
    queryFn: () => networkService.getState(),
    enabled: canViewFullState,
  })

  const warehousesQuery = useQuery({
    queryKey: ['warehouses', 'network-page'],
    queryFn: () => warehouseService.listWarehouses({ limit: 50 }),
  })

  const fleetQuery = useQuery({
    queryKey: ['fleet', 'network-page'],
    queryFn: () => fleetService.listVehicles({ limit: 50 }),
  })

  const activeNodeId =
    selectedNodeId ??
    graphQuery.data?.nodes.find((n) => n.node_type === 'WAREHOUSE')?.id ??
    graphQuery.data?.nodes[0]?.id ??
    null

  const connectionsQuery = useQuery({
    queryKey: ['network', 'connections', activeNodeId],
    queryFn: () => networkService.getNodeConnections(activeNodeId!, true),
    enabled: Boolean(activeNodeId),
  })

  const shortestPathQuery = useQuery({
    queryKey: ['network', 'shortest-path', originId, destId, weightMode],
    queryFn: () =>
      networkService.getShortestPath({
        origin_node_id: originId,
        destination_node_id: destId,
        weight: weightMode,
        directed: true,
      }),
    enabled: Boolean(originId && destId && originId !== destId),
    retry: false,
  })

  const nodesList = graphQuery.data?.nodes ?? []
  const regions = useMemo(() => {
    const set = new Set<string>()
    for (const n of nodesList) {
      if (n.region) set.add(n.region)
    }
    return Array.from(set).sort()
  }, [nodesList])

  const { mapNodes, mapEdges } = useMemo(() => {
    const regionFilteredIds = new Set(
      nodesList
        .filter((n) => selectedRegion === 'ALL' || n.region === selectedRegion)
        .map((n) => n.id),
    )

    const nodes: MapNodePoint[] = showNodes
      ? nodesList
        .filter((n) => regionFilteredIds.has(n.id))
        .map((n) => ({
          id: n.id,
          name: n.name,
          nodeType: n.node_type,
          latitude: n.latitude,
          longitude: n.longitude,
          subtitle: `${n.region ?? 'Bengaluru'} • Degree ${n.degree}`,
          selected: n.id === activeNodeId,
        }))
      : []

    const edges: MapEdgeSegment[] = []
    if (showEdges && geoJsonQuery.data) {
      for (const f of geoJsonQuery.data.features) {
        if (f.geometry.type === 'LineString') {
          const coords = f.geometry.coordinates as [number, number][]
          const src = String(f.properties.source_node_id ?? '')
          const tgt = String(f.properties.target_node_id ?? '')
          if (
            selectedRegion !== 'ALL' &&
            !regionFilteredIds.has(src) &&
            !regionFilteredIds.has(tgt)
          ) {
            continue
          }
          if (coords.length >= 2) {
            edges.push({
              id: f.id,
              from: [coords[0][1], coords[0][0]],
              to: [coords[coords.length - 1][1], coords[coords.length - 1][0]],
              label: `${String(f.properties.road_type ?? 'Corridor')} • ${String(f.properties.distance_km ?? '?')} km`,
            })
          }
        }
      }
    }

    return { mapNodes: nodes, mapEdges: edges }
  }, [nodesList, selectedRegion, showNodes, showEdges, geoJsonQuery.data, activeNodeId])

  const mapVehicles = useMemo<MapVehicleMarker[]>(() => {
    if (!showVehicles) return []
    return (fleetQuery.data?.items ?? [])
      .filter((v) => v.current_latitude !== null && v.current_longitude !== null)
      .map((v) => ({
        id: v.id,
        code: v.vehicle_code,
        status: v.status,
        latitude: v.current_latitude as number,
        longitude: v.current_longitude as number,
        speedKmph: v.current_speed_kmph,
      }))
  }, [showVehicles, fleetQuery.data])

  const highlightedPath = useMemo<[number, number][]>(() => {
    const coords = shortestPathQuery.data?.coordinates ?? []
    // GeoJSON coordinates from backend are [longitude, latitude]
    return coords.map(([lon, lat]) => [lat, lon])
  }, [shortestPathQuery.data])

  const regionDistribution = useMemo(() => {
    const total = nodesList.length || 1
    const counts = new Map<string, { nodes: number; warehouses: number }>()
    for (const n of nodesList) {
      const reg = n.region ?? 'Unassigned'
      const cur = counts.get(reg) ?? { nodes: 0, warehouses: 0 }
      cur.nodes += 1
      if (n.node_type === 'WAREHOUSE') cur.warehouses += 1
      counts.set(reg, cur)
    }
    return Array.from(counts.entries()).map(([region, stats]) => ({
      region,
      nodes: stats.nodes,
      warehouses: stats.warehouses,
      pct: Math.round((stats.nodes / total) * 100),
    }))
  }, [nodesList])

  if (analyticsQuery.isLoading || graphQuery.isLoading) {
    return <LoadingState message="Loading network graph & GIS topology..." />
  }

  if (analyticsQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(analyticsQuery.error)}
        onRetry={() => void analyticsQuery.refetch()}
      />
    )
  }

  const analytics = analyticsQuery.data!
  const validation = validationQuery.data
  const activeNode = nodesList.find((n) => n.id === activeNodeId) ?? null
  const matchingWarehouse = warehousesQuery.data?.items.find((w) => w.network_node_id === activeNode?.id)

  return (
    <div className="space-y-6">
      {/* Top Health Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            value={analytics.network_connectivity_status}
            tone={analytics.network_connectivity_status === 'CONNECTED' ? 'lime' : 'danger'}
            pulse
          />
          {validation && <StatusBadge value={`GRAPH: ${validation.validation_status}`} />}
          <span className="font-telemetry text-xs text-secondary">
            {stateQuery.data?.network.name ?? 'LOGIPULSE Spatial Network'}
          </span>
        </div>

        <button
          type="button"
          onClick={() => setExpandedMap((prev) => !prev)}
          className="inline-flex items-center gap-2 rounded bg-primary-fixed px-3.5 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim transition-colors"
        >
          {expandedMap ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          <span>{expandedMap ? 'Standard Map View' : 'Expand Network Map'}</span>
        </button>
      </div>

      {/* 4 Slim KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Warehouse Hubs"
          value={analytics.warehouse_nodes}
          sublabel={`${analytics.isolated_nodes} isolated nodes`}
        />
        <KpiCard
          label="Customer Endpoints"
          value={analytics.customer_nodes}
          sublabel={`Avg degree ${analytics.average_node_degree.toFixed(2)}`}
        />
        <KpiCard
          label="Corridor Edges"
          value={analytics.total_edges}
          sublabel={`${formatNumber(analytics.total_network_distance_km, 1)} total km`}
          accent="lime"
        />
        <KpiCard
          label="Total Network Nodes"
          value={analytics.total_nodes}
          sublabel={`${analytics.connected_components} connected component(s)`}
        />
      </section>

      {/* Main Map + Inspector Drawer */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 flex flex-col gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={() => setSelectedRegion('ALL')}
                className={`rounded px-2.5 py-1 font-telemetry text-xs font-semibold ${selectedRegion === 'ALL'
                    ? 'bg-primary-fixed text-on-primary-fixed'
                    : 'bg-surface-container text-secondary hover:text-primary'
                  }`}
              >
                All Regions
              </button>
              {regions.map((region) => (
                <button
                  key={region}
                  type="button"
                  onClick={() => setSelectedRegion(region)}
                  className={`rounded px-2.5 py-1 font-telemetry text-xs font-semibold ${selectedRegion === region
                      ? 'bg-primary-fixed text-on-primary-fixed'
                      : 'bg-surface-container text-secondary hover:text-primary'
                    }`}
                >
                  {region}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3 text-xs text-secondary">
              <label className="flex cursor-pointer items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showNodes}
                  onChange={(e) => setShowNodes(e.target.checked)}
                  className="accent-primary-fixed"
                />
                Nodes
              </label>
              <label className="flex cursor-pointer items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showEdges}
                  onChange={(e) => setShowEdges(e.target.checked)}
                  className="accent-primary-fixed"
                />
                Edges
              </label>
              <label className="flex cursor-pointer items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showVehicles}
                  onChange={(e) => setShowVehicles(e.target.checked)}
                  className="accent-primary-fixed"
                />
                Fleet
              </label>
            </div>
          </div>

          <BengaluruNetworkMap
            nodes={mapNodes}
            edges={mapEdges}
            vehicles={mapVehicles}
            highlightedPath={highlightedPath}
            heightClass={expandedMap ? 'h-[640px]' : 'h-[480px]'}
            onSelectNode={(nodeId) => {
              setSelectedNodeId(nodeId)
              setDrawerTab('NODE')
            }}
          />
        </div>

        {/* Right Floating Inspector Drawer */}
        <div className="lg:col-span-4 flex flex-col gap-4 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          <div className="grid grid-cols-2 gap-1 rounded bg-surface-container-lowest p-1 font-display text-xs">
            <button
              type="button"
              onClick={() => setDrawerTab('NODE')}
              className={`rounded py-1.5 font-semibold ${drawerTab === 'NODE'
                  ? 'bg-primary-fixed text-on-primary-fixed'
                  : 'text-secondary hover:text-primary'
                }`}
            >
              Node Inspector
            </button>
            <button
              type="button"
              onClick={() => setDrawerTab('PATH')}
              className={`rounded py-1.5 font-semibold ${drawerTab === 'PATH'
                  ? 'bg-primary-fixed text-on-primary-fixed'
                  : 'text-secondary hover:text-primary'
                }`}
            >
              Shortest Path
            </button>
          </div>

          {drawerTab === 'NODE' ? (
            activeNode ? (
              <div className="space-y-3 text-xs">
                <div className="rounded bg-surface-container p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <StatusBadge value={activeNode.node_type} />
                    <span className="font-telemetry text-[11px] text-outline">
                      Degree: {activeNode.degree}
                    </span>
                  </div>
                  <h3 className="pt-1 font-display text-base font-bold text-primary">
                    {activeNode.name}
                  </h3>
                  <p className="text-secondary">{activeNode.region ?? 'Bengaluru Metro'}</p>
                  <p className="font-telemetry text-[11px] text-outline">
                    {activeNode.latitude.toFixed(4)}°N, {activeNode.longitude.toFixed(4)}°E
                  </p>
                </div>

                {matchingWarehouse && (
                  <div className="rounded border border-primary-fixed/30 bg-surface-container p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-telemetry font-bold text-lime">
                        {matchingWarehouse.warehouse_code}
                      </span>
                      <StatusBadge value={matchingWarehouse.status} />
                    </div>
                    <div className="flex justify-between text-secondary">
                      <span>Storage Used</span>
                      <span className="font-telemetry text-primary">
                        {matchingWarehouse.utilization_percentage}% (
                        {formatNumber(matchingWarehouse.used_capacity)} /{' '}
                        {formatNumber(matchingWarehouse.total_capacity)})
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded bg-surface-container-highest">
                      <div
                        className="h-full bg-primary-fixed"
                        style={{
                          width: `${Math.min(100, matchingWarehouse.utilization_percentage)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                <div className="rounded bg-surface-container p-3 space-y-2">
                  <div className="font-display text-[11px] font-bold uppercase tracking-wider text-outline">
                    Connected Neighbors ({connectionsQuery.data?.connected_nodes.length ?? 0})
                  </div>
                  <div className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
                    {(connectionsQuery.data?.connected_nodes ?? []).map((conn) => (
                      <button
                        key={conn.id}
                        type="button"
                        onClick={() => setSelectedNodeId(conn.id)}
                        className="flex w-full items-center justify-between rounded bg-surface-container-lowest px-2.5 py-2 text-left hover:bg-surface-container-high transition-colors"
                      >
                        <span className="truncate text-primary">{conn.name}</span>
                        <span className="font-telemetry text-[10px] text-lime">
                          {conn.direction}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-secondary">Click any node on the map to inspect connectivity.</p>
            )
          ) : (
            <div className="space-y-3 text-xs">
              <div className="space-y-2 rounded bg-surface-container p-3">
                <label className="block font-display text-[11px] font-bold uppercase text-outline">
                  Origin Node
                </label>
                <select
                  value={originId}
                  onChange={(e) => setOriginId(e.target.value)}
                  className="w-full rounded border border-surface-container-highest bg-surface-container-lowest px-2.5 py-2 text-primary"
                >
                  <option value="">Select origin node...</option>
                  {nodesList.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.node_type})
                    </option>
                  ))}
                </select>

                <label className="block pt-1 font-display text-[11px] font-bold uppercase text-outline">
                  Destination Node
                </label>
                <select
                  value={destId}
                  onChange={(e) => setDestId(e.target.value)}
                  className="w-full rounded border border-surface-container-highest bg-surface-container-lowest px-2.5 py-2 text-primary"
                >
                  <option value="">Select destination node...</option>
                  {nodesList.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.name} ({n.node_type})
                    </option>
                  ))}
                </select>

                <div className="flex gap-2 pt-2">
                  {(['distance', 'travel_time'] as const).map((w) => (
                    <button
                      key={w}
                      type="button"
                      onClick={() => setWeightMode(w)}
                      className={`flex-1 rounded py-1.5 font-telemetry font-semibold uppercase ${weightMode === w
                          ? 'bg-primary-fixed text-on-primary-fixed'
                          : 'bg-surface-container-lowest text-secondary'
                        }`}
                    >
                      {w.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              {shortestPathQuery.isError && (
                <ErrorState
                  title="No route found"
                  message={getApiErrorMessage(shortestPathQuery.error)}
                />
              )}

              {shortestPathQuery.data && (
                <div className="rounded border border-primary-fixed/40 bg-surface-container p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 font-display font-bold text-lime">
                      <RouteIcon className="h-4 w-4" />
                      Dijkstra Optimal Path
                    </span>
                    <span className="font-telemetry text-primary">
                      {shortestPathQuery.data.total_distance_km.toFixed(2)} km
                    </span>
                  </div>
                  <p className="font-telemetry text-secondary">
                    Est. Travel Time:{' '}
                    {shortestPathQuery.data.estimated_travel_minutes?.toFixed(0) ?? 'N/A'} mins •{' '}
                    {shortestPathQuery.data.ordered_nodes.length} hops
                  </p>
                  <ol className="space-y-1 pl-4 list-decimal text-on-surface">
                    {shortestPathQuery.data.ordered_nodes.map((step) => (
                      <li key={step.id}>{step.name}</li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}

          {!canViewFullState && (
            <UnavailableNotice
              title="Scoped Network View"
              description="/network/state is restricted to Admin, Operations Manager, and Analyst roles. Displaying /network/geojson & graph data."
            />
          )}
        </div>
      </section>

      {/* Bottom Insights Strip */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-6 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-display text-xs font-bold uppercase tracking-wider text-outline">
              Regional Node Distribution
            </span>
            <span className="font-telemetry text-xs text-lime">
              {regions.length} Active Sectors
            </span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {regionDistribution.map((r) => (
              <div key={r.region} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="truncate font-medium text-primary">{r.region}</span>
                  <span className="font-telemetry font-bold text-lime">{r.pct}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded bg-surface-container-high">
                  <div className="h-full bg-primary-fixed" style={{ width: `${r.pct}%` }} />
                </div>
                <span className="block font-telemetry text-[10px] text-outline">
                  {r.nodes} nodes • {r.warehouses} hubs
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-6 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-primary-fixed bg-primary-fixed/10 text-lime font-telemetry text-xs font-bold">
              {(analytics.graph_density * 100).toFixed(1)}%
            </div>
            <div>
              <div className="flex items-center gap-2">
                <Network className="h-4 w-4 text-lime" />
                <span className="font-display text-sm font-bold text-primary">
                  Graph Topology Validation
                </span>
              </div>
              <p className="font-telemetry text-xs text-secondary">
                {analytics.total_nodes} Nodes • Density {analytics.graph_density.toFixed(4)} • Avg
                Travel {analytics.average_travel_time_minutes?.toFixed(1) ?? 'N/A'} mins
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs font-telemetry">
            <ShieldCheck className="h-4 w-4 text-lime" />
            <span className="text-primary">
              Errors: {validation?.error_count ?? 0} • Warnings: {validation?.warning_count ?? 0}
            </span>
          </div>
        </div>
      </section>
    </div>
  )
}


import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  Download,
  MapPin,
  Plus,
  RefreshCw,
  Truck,
  Wrench,
} from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import {
  BengaluruNetworkMap,
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
import {
  formatDateTimeShort,
  formatNumber,
  formatPercent,
  getApiErrorMessage,
} from '@/lib/formatters'
import { fleetService } from '@/services/fleet.service'
import { warehouseService } from '@/services/warehouse.service'
import { useAuth } from '@/stores/auth-context'
import type { VehicleStatus, VehicleType } from '@/types/fleet'

const VEHICLE_STATUS_FILTERS: readonly ('ALL' | VehicleStatus)[] = [
  'ALL',
  'AVAILABLE',
  'IN_TRANSIT',
  'BREAKDOWN',
  'MAINTENANCE',
  'IDLE',
  'OFFLINE',
]

export function FleetMonitoringPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const canOperateFleet = hasAnyRole(user?.role, ACTION_PERMISSIONS.FLEET_OPERATE)
  const canManageFleet = hasAnyRole(user?.role, ACTION_PERMISSIONS.FLEET_MANAGE)

  const [statusFilter, setStatusFilter] = useState<'ALL' | VehicleStatus>('ALL')
  const [searchText, setSearchText] = useState('')
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null)
  const [statusReason, setStatusReason] = useState('')
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [newVehicleCode, setNewVehicleCode] = useState('')
  const [newRegNumber, setNewRegNumber] = useState('')
  const [newType, setNewType] = useState<VehicleType>('HEAVY_TRUCK')
  const [newCapacity, setNewCapacity] = useState('1500')
  const [newManufacturer, setNewManufacturer] = useState('')
  const [newModel, setNewModel] = useState('')
  const [newWarehouseId, setNewWarehouseId] = useState('')

  const summaryQuery = useQuery({
    queryKey: ['fleet', 'summary'],
    queryFn: () => fleetService.getSummary(),
    refetchInterval: 10_000,
  })

  const vehiclesQuery = useQuery({
    queryKey: ['fleet', 'vehicles'],
    queryFn: () => fleetService.listVehicles({ limit: 100 }),
    refetchInterval: 10_000,
  })

  const warehousesQuery = useQuery({
    queryKey: ['warehouses', 'fleet-ref'],
    queryFn: () => warehouseService.listWarehouses({ limit: 50 }),
  })

  const vehicles = vehiclesQuery.data?.items ?? []

  const filteredVehicles = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    return vehicles.filter((v) => {
      if (statusFilter !== 'ALL' && v.status !== statusFilter) return false
      if (!q) return true
      return (
        v.vehicle_code.toLowerCase().includes(q) ||
        v.registration_number.toLowerCase().includes(q) ||
        (v.manufacturer ?? '').toLowerCase().includes(q) ||
        (v.model ?? '').toLowerCase().includes(q)
      )
    })
  }, [vehicles, statusFilter, searchText])

  const selectedVehicle = useMemo(
    () =>
      vehicles.find((v) => v.id === selectedVehicleId) ??
      filteredVehicles[0] ??
      vehicles[0] ??
      null,
    [vehicles, filteredVehicles, selectedVehicleId],
  )

  const historyQuery = useQuery({
    queryKey: ['fleet', 'history', selectedVehicle?.id],
    queryFn: () => fleetService.getLocationHistory(selectedVehicle!.id, { limit: 10 }),
    enabled: Boolean(selectedVehicle?.id),
  })

  const statusMutation = useMutation({
    mutationFn: ({ vehicleId, status }: { vehicleId: string; status: VehicleStatus }) =>
      fleetService.updateVehicleStatus(vehicleId, {
        status,
        reason: statusReason.trim() || `Updated to ${status} via Fleet Monitoring`,
      }),
    onSuccess: (res) => {
      setActionErr(null)
      setActionMsg(`Vehicle ${res.vehicle.vehicle_code} updated to ${res.vehicle.status}.`)
      setStatusReason('')
      void queryClient.invalidateQueries({ queryKey: ['fleet'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => {
      setActionMsg(null)
      setActionErr(getApiErrorMessage(err))
    },
  })

  const createMutation = useMutation({
    mutationFn: () =>
      fleetService.createVehicle({
        vehicle_code: newVehicleCode.trim(),
        registration_number: newRegNumber.trim(),
        vehicle_type: newType,
        capacity_kg: Number(newCapacity) || 1000,
        manufacturer: newManufacturer.trim() || undefined,
        model: newModel.trim() || undefined,
        home_warehouse_id: newWarehouseId || null,
        is_active: true,
      }),
    onSuccess: (created) => {
      setActionErr(null)
      setActionMsg(`Registered vehicle ${created.vehicle_code}.`)
      setCreateModalOpen(false)
      setNewVehicleCode('')
      setNewRegNumber('')
      setSelectedVehicleId(created.id)
      void queryClient.invalidateQueries({ queryKey: ['fleet'] })
    },
    onError: (err) => {
      setActionErr(getApiErrorMessage(err))
    },
  })

  const mapVehicles = useMemo<MapVehicleMarker[]>(() => {
    return filteredVehicles
      .filter((v) => v.current_latitude !== null && v.current_longitude !== null)
      .map((v) => ({
        id: v.id,
        code: v.vehicle_code,
        status: v.status,
        latitude: v.current_latitude as number,
        longitude: v.current_longitude as number,
        speedKmph: v.current_speed_kmph,
        selected: v.id === selectedVehicle?.id,
      }))
  }, [filteredVehicles, selectedVehicle?.id])

  function handleExportCsv() {
    const header = 'vehicle_code,registration_number,type,status,load_kg,capacity_kg,lat,lon\n'
    const rows = filteredVehicles
      .map(
        (v) =>
          `${v.vehicle_code},${v.registration_number},${v.vehicle_type},${v.status},${v.current_load_kg},${v.capacity_kg},${v.current_latitude ?? ''},${v.current_longitude ?? ''}`,
      )
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'logipulse-fleet.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  function handleCreateSubmit(e: FormEvent) {
    e.preventDefault()
    createMutation.mutate()
  }

  if (summaryQuery.isLoading || vehiclesQuery.isLoading) {
    return <LoadingState message="Synchronizing fleet telemetry & vehicle registry..." />
  }

  if (summaryQuery.isError || vehiclesQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(summaryQuery.error ?? vehiclesQuery.error)}
        onRetry={() => {
          void summaryQuery.refetch()
          void vehiclesQuery.refetch()
        }}
      />
    )
  }

  const summary = summaryQuery.data!

  return (
    <div className="space-y-6">
      {/* Stream Sync Context Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-3 font-telemetry text-xs">
          <span className="inline-flex items-center gap-1.5 text-lime font-bold">
            <span className="h-2 w-2 rounded-full bg-lime animate-pulse" />
            FLEET TELEMETRY SYNCHRONIZED
          </span>
          <span className="text-secondary">
            {summary.active_vehicles}/{summary.total_vehicles} Active Assets
          </span>
          <span className="text-outline">Updated {formatDateTimeShort(summary.generated_at)}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void vehiclesQuery.refetch()}
            className="inline-flex items-center gap-1.5 rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 font-telemetry text-xs text-primary hover:bg-surface-container-high"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          {canManageFleet && (
            <button
              type="button"
              onClick={() => setCreateModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3 py-1.5 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Vehicle
            </button>
          )}
        </div>
      </div>

      {/* 6 KPI Summary Cards */}
      <section className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="Total Vehicles" value={summary.total_vehicles} />
        <KpiCard label="Available" value={summary.available_vehicles} accent="success" />
        <KpiCard label="In Transit" value={summary.in_transit_vehicles} accent="info" />
        <KpiCard label="Breakdown" value={summary.breakdown_vehicles} accent="danger" />
        <KpiCard label="Maintenance" value={summary.maintenance_vehicles} accent="warn" />
        <KpiCard
          label="Load Utilization"
          value={formatPercent(summary.fleet_utilization_percentage)}
          sublabel={`${formatNumber(summary.current_load_kg)} / ${formatNumber(summary.total_capacity_kg)} kg`}
          accent="lime"
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

      {/* Main Split: Map (7 cols) + Vehicle Details Inspector (5 cols) */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7 flex flex-col gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          <div className="flex flex-wrap gap-1.5">
            {VEHICLE_STATUS_FILTERS.map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`rounded px-2.5 py-1 font-telemetry text-xs font-semibold transition-colors ${statusFilter === st
                    ? 'bg-primary-fixed text-on-primary-fixed'
                    : 'bg-surface-container text-secondary hover:text-primary'
                  }`}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
          </div>

          <BengaluruNetworkMap
            vehicles={mapVehicles}
            heightClass="h-[440px]"
            onSelectVehicle={(id) => setSelectedVehicleId(id)}
          />
        </div>

        {/* Right: Vehicle Diagnostics & Status Actions */}
        <div className="lg:col-span-5 flex flex-col justify-between gap-4 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          {selectedVehicle ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between border-b border-surface-container-highest pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Truck className="h-5 w-5 text-lime" />
                    <h2 className="font-display text-lg font-bold text-primary">
                      {selectedVehicle.vehicle_code}
                    </h2>
                  </div>
                  <p className="mt-0.5 font-telemetry text-xs text-secondary">
                    {selectedVehicle.registration_number} • {selectedVehicle.vehicle_type}
                  </p>
                  <p className="text-xs text-outline">
                    {selectedVehicle.manufacturer ?? '—'} {selectedVehicle.model ?? ''}
                  </p>
                </div>
                <StatusBadge
                  value={selectedVehicle.status}
                  pulse={selectedVehicle.status === 'BREAKDOWN'}
                />
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded bg-surface-container p-3">
                  <span className="font-display text-[10px] font-bold uppercase text-outline">
                    Current GPS Coordinates
                  </span>
                  <div className="mt-1 font-telemetry font-semibold text-primary">
                    {selectedVehicle.current_latitude !== null &&
                      selectedVehicle.current_longitude !== null
                      ? `${selectedVehicle.current_latitude.toFixed(4)}°N, ${selectedVehicle.current_longitude.toFixed(4)}°E`
                      : 'No GPS Fix'}
                  </div>
                </div>
                <div className="rounded bg-surface-container p-3">
                  <span className="font-display text-[10px] font-bold uppercase text-outline">
                    Speed &amp; Heading
                  </span>
                  <div className="mt-1 font-telemetry font-semibold text-primary">
                    {selectedVehicle.current_speed_kmph?.toFixed(1) ?? '0'} km/h •{' '}
                    {selectedVehicle.heading_degrees?.toFixed(0) ?? '0'}°
                  </div>
                </div>
              </div>

              {/* Cargo Load Bar */}
              <div className="rounded bg-surface-container p-3 space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-display text-[11px] font-bold uppercase text-outline">
                    Payload Capacity
                  </span>
                  <span className="font-telemetry font-bold text-primary">
                    {formatNumber(selectedVehicle.current_load_kg)} /{' '}
                    {formatNumber(selectedVehicle.capacity_kg)} kg
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-surface-container-highest">
                  <div
                    className="h-full bg-primary-fixed"
                    style={{
                      width: `${Math.min(
                        100,
                        (selectedVehicle.current_load_kg / Math.max(1, selectedVehicle.capacity_kg)) *
                        100,
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {/* Recent Location Breadcrumbs */}
              <div className="rounded bg-surface-container p-3 space-y-2">
                <div className="flex items-center gap-1.5 font-display text-[11px] font-bold uppercase text-outline">
                  <MapPin className="h-3.5 w-3.5 text-lime" />
                  Location History ({historyQuery.data?.total ?? 0})
                </div>
                <div className="max-h-28 space-y-1 overflow-y-auto font-telemetry text-[11px]">
                  {(historyQuery.data?.items ?? []).slice(0, 4).map((pt) => (
                    <div
                      key={pt.id}
                      className="flex justify-between text-secondary border-b border-surface-container-highest/40 pb-1"
                    >
                      <span>
                        {pt.latitude.toFixed(4)}, {pt.longitude.toFixed(4)}
                      </span>
                      <span>
                        {pt.source} • {formatDateTimeShort(pt.recorded_at)}
                      </span>
                    </div>
                  ))}
                  {historyQuery.data?.items.length === 0 && (
                    <span className="text-outline">No historical location points recorded.</span>
                  )}
                </div>
              </div>

              {/* Status Controls */}
              {canOperateFleet ? (
                <div className="space-y-2 border-t border-surface-container-highest pt-3">
                  <input
                    type="text"
                    value={statusReason}
                    onChange={(e) => setStatusReason(e.target.value)}
                    placeholder="Optional audit reason for status update..."
                    className="w-full rounded border border-surface-container-highest bg-surface-container-lowest px-3 py-1.5 text-xs text-primary"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      disabled={statusMutation.isPending}
                      onClick={() =>
                        statusMutation.mutate({
                          vehicleId: selectedVehicle.id,
                          status: 'AVAILABLE',
                        })
                      }
                      className="rounded border border-[#22C55E]/40 bg-[#22C55E]/15 py-2 font-display text-xs font-bold text-[#22C55E] hover:bg-[#22C55E]/25"
                    >
                      Mark Available
                    </button>
                    <button
                      type="button"
                      disabled={statusMutation.isPending}
                      onClick={() =>
                        statusMutation.mutate({
                          vehicleId: selectedVehicle.id,
                          status: 'BREAKDOWN',
                        })
                      }
                      className="rounded border border-[#EF4444]/40 bg-[#EF4444]/15 py-2 font-display text-xs font-bold text-[#F87171] hover:bg-[#EF4444]/25"
                    >
                      Report Breakdown
                    </button>
                    <button
                      type="button"
                      disabled={statusMutation.isPending}
                      onClick={() =>
                        statusMutation.mutate({
                          vehicleId: selectedVehicle.id,
                          status: 'MAINTENANCE',
                        })
                      }
                      className="flex items-center justify-center gap-1 rounded border border-[#F59E0B]/40 bg-[#F59E0B]/15 py-2 font-display text-xs font-bold text-[#FBBF24]"
                    >
                      <Wrench className="h-3.5 w-3.5" />
                      Maintenance
                    </button>
                    <button
                      type="button"
                      disabled={statusMutation.isPending}
                      onClick={() =>
                        statusMutation.mutate({
                          vehicleId: selectedVehicle.id,
                          status: 'IN_TRANSIT',
                        })
                      }
                      className="flex items-center justify-center gap-1 rounded border border-[#3B82F6]/40 bg-[#3B82F6]/15 py-2 font-display text-xs font-bold text-[#60A5FA]"
                    >
                      <Activity className="h-3.5 w-3.5" />
                      In Transit
                    </button>
                  </div>
                </div>
              ) : (
                <UnavailableNotice
                  title="Read-Only Fleet Role"
                  description="Vehicle status updates require ADMIN, OPERATIONS_MANAGER, or FLEET_MANAGER permissions."
                />
              )}
            </div>
          ) : (
            <EmptyState title="No vehicle selected" description="Select a vehicle from the map or table." />
          )}
        </div>
      </section>

      {/* Active Fleet Directory Table */}
      <section className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-base font-bold text-primary">
              Active Fleet Directory ({filteredVehicles.length})
            </h2>
            <p className="text-xs text-secondary">
              Backend vehicle registry from `/api/v1/fleet/vehicles`
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search code, plate, model..."
              className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 text-xs text-primary placeholder:text-outline focus:border-primary-fixed focus:outline-none"
            />
            <button
              type="button"
              onClick={handleExportCsv}
              className="inline-flex items-center gap-1.5 rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 font-telemetry text-xs text-primary hover:bg-surface-container-high"
            >
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-surface-container-highest bg-surface-container-lowest font-display text-[11px] uppercase tracking-wider text-outline">
                <th className="px-3 py-3">Vehicle ID</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Capacity Utilization</th>
                <th className="px-3 py-3">Coordinates &amp; Speed</th>
                <th className="px-3 py-3">Home Warehouse</th>
                <th className="px-3 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-highest/50">
              {filteredVehicles.map((v) => {
                const loadPct = Math.round((v.current_load_kg / Math.max(1, v.capacity_kg)) * 100)
                return (
                  <tr
                    key={v.id}
                    onClick={() => setSelectedVehicleId(v.id)}
                    className={`cursor-pointer transition-colors hover:bg-surface-container ${selectedVehicle?.id === v.id ? 'bg-surface-container/80' : ''
                      }`}
                  >
                    <td className="px-3 py-3">
                      <div className="font-display font-bold text-primary">{v.vehicle_code}</div>
                      <div className="font-telemetry text-[11px] text-outline">
                        {v.registration_number} • {v.vehicle_type}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge value={v.status} />
                    </td>
                    <td className="px-3 py-3">
                      <div className="w-36 space-y-1">
                        <div className="flex justify-between font-telemetry text-[11px]">
                          <span className="font-bold text-primary">{loadPct}%</span>
                          <span className="text-outline">
                            {formatNumber(v.current_load_kg)}/{formatNumber(v.capacity_kg)}kg
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded bg-surface-container-highest">
                          <div className="h-full bg-primary-fixed" style={{ width: `${loadPct}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 font-telemetry text-secondary">
                      {v.current_latitude !== null && v.current_longitude !== null
                        ? `${v.current_latitude.toFixed(3)}, ${v.current_longitude.toFixed(3)} • ${v.current_speed_kmph ?? 0} km/h`
                        : '—'}
                    </td>
                    <td className="px-3 py-3 font-telemetry text-secondary">
                      {v.home_warehouse?.warehouse_code ?? 'Unassigned'}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedVehicleId(v.id)}
                        className="rounded bg-surface-container-high px-2.5 py-1 font-telemetry font-semibold text-primary-fixed hover:bg-primary-fixed hover:text-on-primary-fixed"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {filteredVehicles.length === 0 && (
            <EmptyState
              title="No matching vehicles"
              description="Adjust your status filter or search query."
            />
          )}
        </div>
      </section>

      {/* Register Vehicle Modal */}
      <Modal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Register Fleet Vehicle"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Vehicle Code
              </label>
              <input
                required
                value={newVehicleCode}
                onChange={(e) => setNewVehicleCode(e.target.value)}
                placeholder="TRK-009"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Registration Plate
              </label>
              <input
                required
                value={newRegNumber}
                onChange={(e) => setNewRegNumber(e.target.value)}
                placeholder="KA-01-EQ-1009"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Type</label>
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value as VehicleType)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                <option value="HEAVY_TRUCK">HEAVY_TRUCK</option>
                <option value="MEDIUM_TRUCK">MEDIUM_TRUCK</option>
                <option value="DELIVERY_VAN">DELIVERY_VAN</option>
                <option value="ELECTRIC_VAN">ELECTRIC_VAN</option>
              </select>
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Capacity (kg)
              </label>
              <input
                required
                type="number"
                min="1"
                value={newCapacity}
                onChange={(e) => setNewCapacity(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Manufacturer
              </label>
              <input
                value={newManufacturer}
                onChange={(e) => setNewManufacturer(e.target.value)}
                placeholder="Tata Motors"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Model</label>
              <input
                value={newModel}
                onChange={(e) => setNewModel(e.target.value)}
                placeholder="Prima 2830.K"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
          </div>
          <div>
            <label className="font-display text-[11px] uppercase text-secondary">
              Home Warehouse
            </label>
            <select
              value={newWarehouseId}
              onChange={(e) => setNewWarehouseId(e.target.value)}
              className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
            >
              <option value="">None / Unassigned</option>
              {(warehousesQuery.data?.items ?? []).map((w) => (
                <option key={w.id} value={w.id}>
                  {w.warehouse_code} — {w.network_node?.name ?? w.warehouse_type}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="rounded bg-surface-container px-4 py-2 text-secondary hover:text-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="rounded bg-primary-fixed px-4 py-2 font-display font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
            >
              {createMutation.isPending ? 'Saving...' : 'Create Vehicle'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}


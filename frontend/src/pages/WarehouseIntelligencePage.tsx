import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Boxes, Plus, Warehouse } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import { BengaluruNetworkMap, type MapNodePoint } from '@/components/maps/BengaluruNetworkMap'
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
import { formatNumber, formatPercent, getApiErrorMessage } from '@/lib/formatters'
import { warehouseService } from '@/services/warehouse.service'
import { useAuth } from '@/stores/auth-context'
import type { MovementType, WarehouseStatus } from '@/types/warehouse'

export function WarehouseIntelligencePage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const canViewSummary = hasAnyRole(user?.role, ACTION_PERMISSIONS.WAREHOUSE_SUMMARY)
  const canManageWarehouse = hasAnyRole(user?.role, ACTION_PERMISSIONS.WAREHOUSE_MANAGE)
  const canManageInventory = hasAnyRole(user?.role, ACTION_PERMISSIONS.INVENTORY_MANAGE)

  const [regionFilter, setRegionFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [searchText, setSearchText] = useState('')
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const [skuModalOpen, setSkuModalOpen] = useState(false)
  const [skuCode, setSkuCode] = useState('')
  const [skuName, setSkuName] = useState('')
  const [skuCategory, setSkuCategory] = useState('Electronics')
  const [skuQty, setSkuQty] = useState('50')
  const [skuReorder, setSkuReorder] = useState('15')
  const [skuUnit, setSkuUnit] = useState('units')

  const [movementModalItemId, setMovementModalItemId] = useState<string | null>(null)
  const [movementType, setMovementType] = useState<MovementType>('STOCK_RECEIVED')
  const [movementQty, setMovementQty] = useState('10')
  const [adjustmentDir, setAdjustmentDir] = useState<'INCREASE' | 'DECREASE'>('INCREASE')
  const [movementRef, setMovementRef] = useState('')

  const summaryQuery = useQuery({
    queryKey: ['warehouses', 'summary'],
    queryFn: () => warehouseService.getSummary(),
    enabled: canViewSummary,
  })

  const warehousesQuery = useQuery({
    queryKey: ['warehouses', 'list'],
    queryFn: () => warehouseService.listWarehouses({ limit: 50 }),
    refetchInterval: 15_000,
  })

  const lowStockQuery = useQuery({
    queryKey: ['inventory', 'low-stock'],
    queryFn: () => warehouseService.listLowStock({ limit: 50 }),
  })

  const warehouses = warehousesQuery.data?.items ?? []

  const regions = useMemo(() => {
    const set = new Set<string>()
    for (const w of warehouses) {
      if (w.network_node?.region) set.add(w.network_node.region)
    }
    return Array.from(set).sort()
  }, [warehouses])

  const filteredWarehouses = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    return warehouses.filter((w) => {
      if (regionFilter !== 'ALL' && w.network_node?.region !== regionFilter) return false
      if (statusFilter !== 'ALL' && w.status !== statusFilter) return false
      if (!q) return true
      return (
        w.warehouse_code.toLowerCase().includes(q) ||
        (w.network_node?.name ?? '').toLowerCase().includes(q) ||
        (w.manager_name ?? '').toLowerCase().includes(q)
      )
    })
  }, [warehouses, regionFilter, statusFilter, searchText])

  const selectedWarehouse = useMemo(
    () =>
      warehouses.find((w) => w.id === selectedWarehouseId) ??
      filteredWarehouses[0] ??
      warehouses[0] ??
      null,
    [warehouses, filteredWarehouses, selectedWarehouseId],
  )

  const inventoryQuery = useQuery({
    queryKey: ['warehouses', 'inventory', selectedWarehouse?.id],
    queryFn: () => warehouseService.listInventory(selectedWarehouse!.id, { limit: 100 }),
    enabled: Boolean(selectedWarehouse?.id),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: WarehouseStatus }) =>
      warehouseService.updateWarehouse(id, { status }),
    onSuccess: (updated) => {
      setActionErr(null)
      setActionMsg(`Updated ${updated.warehouse_code} status to ${updated.status}.`)
      void queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const addSkuMutation = useMutation({
    mutationFn: () =>
      warehouseService.createInventoryItem(selectedWarehouse!.id, {
        sku: skuCode.trim(),
        product_name: skuName.trim(),
        category: skuCategory.trim() || undefined,
        quantity: Number(skuQty) || 0,
        reorder_level: Number(skuReorder) || 10,
        unit: skuUnit.trim() || 'units',
      }),
    onSuccess: (created) => {
      setActionErr(null)
      setActionMsg(`Added SKU ${created.sku} to ${selectedWarehouse?.warehouse_code}.`)
      setSkuModalOpen(false)
      setSkuCode('')
      setSkuName('')
      void queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      void queryClient.invalidateQueries({ queryKey: ['inventory'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const movementMutation = useMutation({
    mutationFn: () =>
      warehouseService.recordMovement(movementModalItemId!, {
        movement_type: movementType,
        quantity: Number(movementQty) || 1,
        adjustment_type: movementType === 'STOCK_ADJUSTMENT' ? adjustmentDir : undefined,
        reference: movementRef.trim() || undefined,
      }),
    onSuccess: () => {
      setActionErr(null)
      setActionMsg('Recorded inventory movement.')
      setMovementModalItemId(null)
      setMovementRef('')
      void queryClient.invalidateQueries({ queryKey: ['warehouses'] })
      void queryClient.invalidateQueries({ queryKey: ['inventory'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const mapNodes = useMemo<MapNodePoint[]>(() => {
    return filteredWarehouses
      .filter((w) => w.network_node)
      .map((w) => ({
        id: w.id,
        name: `${w.warehouse_code} • ${w.network_node!.name}`,
        nodeType: 'WAREHOUSE',
        latitude: w.network_node!.latitude,
        longitude: w.network_node!.longitude,
        subtitle: `${w.status} (${w.utilization_percentage}%)`,
        selected: w.id === selectedWarehouse?.id,
      }))
  }, [filteredWarehouses, selectedWarehouse?.id])

  function handleAddSku(e: FormEvent) {
    e.preventDefault()
    if (!selectedWarehouse) return
    addSkuMutation.mutate()
  }

  function handleRecordMovement(e: FormEvent) {
    e.preventDefault()
    if (!movementModalItemId) return
    movementMutation.mutate()
  }

  if (warehousesQuery.isLoading) {
    return <LoadingState message="Loading Bengaluru warehouse facilities..." />
  }

  if (warehousesQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(warehousesQuery.error)}
        onRetry={() => void warehousesQuery.refetch()}
      />
    )
  }

  const summary = summaryQuery.data

  return (
    <div className="space-y-6">
      {/* Filter Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low px-4 py-3">
        <div className="flex items-center gap-2 font-telemetry text-xs text-lime">
          <span className="h-2 w-2 rounded-full bg-lime animate-pulse" />
          <span>{warehouses.length} WAREHOUSE NODES MONITORED</span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select
            value={regionFilter}
            onChange={(e) => setRegionFilter(e.target.value)}
            className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 text-primary"
          >
            <option value="ALL">Region: All</option>
            {regions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 text-primary"
          >
            <option value="ALL">Status: All</option>
            <option value="OPERATIONAL">OPERATIONAL</option>
            <option value="DEGRADED">DEGRADED</option>
            <option value="MAINTENANCE">MAINTENANCE</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </div>
      </div>

      {/* 4 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Warehouses"
          value={summary?.total_warehouses ?? warehouses.length}
          sublabel={
            summary
              ? `${summary.operational_warehouses} operational • ${summary.degraded_warehouses} degraded`
              : `${warehouses.filter((w) => w.status === 'OPERATIONAL').length} operational`
          }
          icon={<Warehouse className="h-4 w-4" />}
        />
        <KpiCard
          label="Storage Utilization"
          value={formatPercent(summary?.average_utilization_percentage ?? null)}
          sublabel={
            summary
              ? `${formatNumber(summary.used_storage_capacity)} / ${formatNumber(summary.total_storage_capacity)}`
              : 'Summary restricted for role'
          }
          accent="lime"
        />
        <KpiCard
          label="Low Stock Alerts"
          value={lowStockQuery.data?.total ?? summary?.low_stock_items ?? 0}
          sublabel="Items at or below reorder threshold"
          accent={(lowStockQuery.data?.total ?? 0) > 0 ? 'warn' : 'success'}
          icon={<AlertTriangle className="h-4 w-4" />}
        />
        <KpiCard
          label="SKU Records"
          value={summary?.total_inventory_records ?? inventoryQuery.data?.total ?? 0}
          sublabel={`${summary?.out_of_stock_items ?? 0} out of stock`}
          icon={<Boxes className="h-4 w-4" />}
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

      {/* Split Workspace: Map (7 cols) + Facility Inspector (5 cols) */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          <BengaluruNetworkMap
            nodes={mapNodes}
            heightClass="h-[420px]"
            onSelectNode={(warehouseId) => setSelectedWarehouseId(warehouseId)}
          />
        </div>

        <div className="lg:col-span-5 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 flex flex-col justify-between gap-4">
          {selectedWarehouse ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between border-b border-surface-container-highest pb-3">
                <div>
                  <span className="font-telemetry text-xs font-bold text-lime">
                    {selectedWarehouse.warehouse_code} • {selectedWarehouse.warehouse_type}
                  </span>
                  <h2 className="mt-1 font-display text-lg font-bold text-primary">
                    {selectedWarehouse.network_node?.name ?? selectedWarehouse.warehouse_code}
                  </h2>
                  <p className="text-xs text-secondary">
                    {selectedWarehouse.network_node?.address ?? selectedWarehouse.network_node?.region}
                  </p>
                </div>
                <StatusBadge value={selectedWarehouse.status} />
              </div>

              <div className="rounded bg-surface-container p-3 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-secondary">Capacity Utilization</span>
                  <span className="font-telemetry font-bold text-primary">
                    {selectedWarehouse.utilization_percentage}% ({formatNumber(selectedWarehouse.used_capacity)} /{' '}
                    {formatNumber(selectedWarehouse.total_capacity)})
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded bg-surface-container-highest">
                  <div
                    className="h-full bg-primary-fixed"
                    style={{
                      width: `${Math.min(100, selectedWarehouse.utilization_percentage)}%`,
                    }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded bg-surface-container p-3">
                  <span className="text-outline uppercase font-display text-[10px]">Manager</span>
                  <div className="mt-1 font-medium text-primary">
                    {selectedWarehouse.manager_name ?? 'Unassigned'}
                  </div>
                </div>
                <div className="rounded bg-surface-container p-3">
                  <span className="text-outline uppercase font-display text-[10px]">Contact</span>
                  <div className="mt-1 font-telemetry text-primary">
                    {selectedWarehouse.contact_number ?? '—'}
                  </div>
                </div>
              </div>

              {canManageWarehouse ? (
                <div className="space-y-2 border-t border-surface-container-highest pt-3">
                  <span className="block font-display text-[11px] font-bold uppercase text-outline">
                    Update Facility Operational Status
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    {(
                      ['OPERATIONAL', 'DEGRADED', 'MAINTENANCE', 'CLOSED'] as WarehouseStatus[]
                    ).map((st) => (
                      <button
                        key={st}
                        type="button"
                        disabled={statusMutation.isPending || selectedWarehouse.status === st}
                        onClick={() =>
                          statusMutation.mutate({ id: selectedWarehouse.id, status: st })
                        }
                        className={`rounded border py-2 font-display text-xs font-bold transition-colors ${
                          selectedWarehouse.status === st
                            ? 'border-primary-fixed bg-primary-fixed/15 text-lime'
                            : 'border-surface-container-highest bg-surface-container text-secondary hover:text-primary'
                        }`}
                      >
                        {st}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <UnavailableNotice
                  title="Facility Mutation Restricted"
                  description="Only ADMIN or WAREHOUSE_MANAGER roles can modify warehouse operational status."
                />
              )}
            </div>
          ) : (
            <EmptyState title="No warehouses found" description="Verify seeded warehouse data in backend." />
          )}
        </div>
      </section>

      {/* Warehouse Directory Table */}
      <section className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-base font-bold text-primary">
            Warehouse Directory ({filteredWarehouses.length})
          </h2>
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search warehouse code, name, manager..."
            className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 text-xs text-primary placeholder:text-outline focus:border-primary-fixed focus:outline-none"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-surface-container-highest bg-surface-container-lowest font-display text-[11px] uppercase tracking-wider text-outline">
                <th className="px-3 py-3">Code</th>
                <th className="px-3 py-3">Facility Name</th>
                <th className="px-3 py-3">Region</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">Utilization</th>
                <th className="px-3 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-highest/50">
              {filteredWarehouses.map((w) => (
                <tr
                  key={w.id}
                  onClick={() => setSelectedWarehouseId(w.id)}
                  className={`cursor-pointer hover:bg-surface-container ${
                    selectedWarehouse?.id === w.id ? 'bg-surface-container/80' : ''
                  }`}
                >
                  <td className="px-3 py-3 font-telemetry font-bold text-lime">{w.warehouse_code}</td>
                  <td className="px-3 py-3 font-medium text-primary">
                    {w.network_node?.name ?? w.warehouse_type}
                  </td>
                  <td className="px-3 py-3 text-secondary">{w.network_node?.region ?? '—'}</td>
                  <td className="px-3 py-3">
                    <StatusBadge value={w.status} />
                  </td>
                  <td className="px-3 py-3 font-telemetry text-primary">
                    {w.utilization_percentage}% ({formatNumber(w.available_capacity)} free)
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => setSelectedWarehouseId(w.id)}
                      className="rounded bg-surface-container-high px-2.5 py-1 font-telemetry font-semibold text-primary hover:bg-primary-fixed hover:text-on-primary-fixed"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Selected Warehouse Inventory & Stock Movements */}
      {selectedWarehouse && (
        <section className="rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-base font-bold text-primary">
                Facility Inventory — {selectedWarehouse.warehouse_code}
              </h2>
              <p className="text-xs text-secondary">
                Live SKU balances from `/warehouses/{selectedWarehouse.warehouse_code}/inventory`
              </p>
            </div>
            {canManageInventory && (
              <button
                type="button"
                onClick={() => setSkuModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3 py-1.5 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
              >
                <Plus className="h-3.5 w-3.5" />
                Add SKU Item
              </button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-surface-container-highest bg-surface-container-lowest font-display text-[11px] uppercase tracking-wider text-outline">
                  <th className="px-3 py-2.5">SKU</th>
                  <th className="px-3 py-2.5">Product Name</th>
                  <th className="px-3 py-2.5">Category</th>
                  <th className="px-3 py-2.5">Quantity</th>
                  <th className="px-3 py-2.5">Reorder Level</th>
                  <th className="px-3 py-2.5">Stock Status</th>
                  <th className="px-3 py-2.5 text-right">Movement</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-highest/40">
                {(inventoryQuery.data?.items ?? []).map((item) => (
                  <tr key={item.id} className="hover:bg-surface-container">
                    <td className="px-3 py-2.5 font-telemetry font-bold text-lime">{item.sku}</td>
                    <td className="px-3 py-2.5 text-primary">{item.product_name}</td>
                    <td className="px-3 py-2.5 text-secondary">{item.category ?? '—'}</td>
                    <td className="px-3 py-2.5 font-telemetry font-bold text-primary">
                      {item.quantity} {item.unit}
                    </td>
                    <td className="px-3 py-2.5 font-telemetry text-secondary">
                      {item.reorder_level}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge value={item.status} />
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      {canManageInventory ? (
                        <button
                          type="button"
                          onClick={() => setMovementModalItemId(item.id)}
                          className="rounded bg-surface-container-high px-2.5 py-1 font-telemetry text-primary-fixed hover:bg-surface-bright"
                        >
                          Record Movement
                        </button>
                      ) : (
                        <span className="text-outline">Read-only</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(inventoryQuery.data?.items ?? []).length === 0 && (
              <EmptyState
                title="No SKU items in this warehouse"
                description="Add an inventory record to track stock levels."
              />
            )}
          </div>
        </section>
      )}

      {/* Add SKU Modal */}
      <Modal
        open={skuModalOpen}
        onClose={() => setSkuModalOpen(false)}
        title="Add Inventory SKU"
      >
        <form onSubmit={handleAddSku} className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">SKU Code</label>
              <input
                required
                value={skuCode}
                onChange={(e) => setSkuCode(e.target.value)}
                placeholder="ELEC-WH01-99"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Category</label>
              <input
                value={skuCategory}
                onChange={(e) => setSkuCategory(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
          </div>
          <div>
            <label className="font-display text-[11px] uppercase text-secondary">Product Name</label>
            <input
              required
              value={skuName}
              onChange={(e) => setSkuName(e.target.value)}
              placeholder="Autonomous Sensor Module"
              className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Quantity</label>
              <input
                required
                type="number"
                min="0"
                value={skuQty}
                onChange={(e) => setSkuQty(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Reorder Level
              </label>
              <input
                required
                type="number"
                min="0"
                value={skuReorder}
                onChange={(e) => setSkuReorder(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Unit</label>
              <input
                value={skuUnit}
                onChange={(e) => setSkuUnit(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setSkuModalOpen(false)}
              className="rounded bg-surface-container px-4 py-2 text-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={addSkuMutation.isPending}
              className="rounded bg-primary-fixed px-4 py-2 font-display font-bold text-on-primary-fixed"
            >
              Add SKU
            </button>
          </div>
        </form>
      </Modal>

      {/* Stock Movement Modal */}
      <Modal
        open={Boolean(movementModalItemId)}
        onClose={() => setMovementModalItemId(null)}
        title="Record Stock Movement"
      >
        <form onSubmit={handleRecordMovement} className="space-y-3 text-xs">
          <div>
            <label className="font-display text-[11px] uppercase text-secondary">
              Movement Type
            </label>
            <select
              value={movementType}
              onChange={(e) => setMovementType(e.target.value as MovementType)}
              className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
            >
              <option value="STOCK_RECEIVED">STOCK_RECEIVED</option>
              <option value="STOCK_DISPATCHED">STOCK_DISPATCHED</option>
              <option value="STOCK_ADJUSTMENT">STOCK_ADJUSTMENT</option>
            </select>
          </div>

          {movementType === 'STOCK_ADJUSTMENT' && (
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Adjustment Direction
              </label>
              <select
                value={adjustmentDir}
                onChange={(e) => setAdjustmentDir(e.target.value as 'INCREASE' | 'DECREASE')}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                <option value="INCREASE">INCREASE</option>
                <option value="DECREASE">DECREASE</option>
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Quantity</label>
              <input
                required
                type="number"
                min="1"
                value={movementQty}
                onChange={(e) => setMovementQty(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Reference</label>
              <input
                value={movementRef}
                onChange={(e) => setMovementRef(e.target.value)}
                placeholder="PO-2026-01"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setMovementModalItemId(null)}
              className="rounded bg-surface-container px-4 py-2 text-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={movementMutation.isPending}
              className="rounded bg-primary-fixed px-4 py-2 font-display font-bold text-on-primary-fixed"
            >
              Submit Movement
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}


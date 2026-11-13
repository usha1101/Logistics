import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Package, Plus, Truck } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'

import {
  BengaluruNetworkMap,
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
import {
  formatDateTimeShort,
  formatNumber,
  getApiErrorMessage,
} from '@/lib/formatters'
import { fleetService } from '@/services/fleet.service'
import { orderService } from '@/services/order.service'
import { warehouseService } from '@/services/warehouse.service'
import { useAuth } from '@/stores/auth-context'
import {
  PERMITTED_ORDER_STATUS_TRANSITIONS,
  WAREHOUSE_MANAGER_ALLOWED_STATUSES,
  type OrderPriority,
  type OrderStatus,
} from '@/types/order'

const PAGE_SIZE = 10

export function OrderManagementPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const canCreateOrder = hasAnyRole(user?.role, ACTION_PERMISSIONS.ORDER_MANAGE)
  const canUpdateStatus = hasAnyRole(user?.role, ACTION_PERMISSIONS.ORDER_STATUS)
  const canAssignVehicle = hasAnyRole(user?.role, ACTION_PERMISSIONS.ORDER_ASSIGN)

  const [priorityFilter, setPriorityFilter] = useState<'ALL' | OrderPriority>('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | OrderStatus>('ALL')
  const [overdueOnly, setOverdueOnly] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [page, setPage] = useState(0)
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionErr, setActionErr] = useState<string | null>(null)

  const [assignModalOpen, setAssignModalOpen] = useState(false)
  const [targetVehicleId, setTargetVehicleId] = useState<string>('')
  const [assignReason, setAssignReason] = useState('')

  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [newOrderNumber, setNewOrderNumber] = useState('')
  const [newCustomerId, setNewCustomerId] = useState('')
  const [newWarehouseId, setNewWarehouseId] = useState('')
  const [newPriority, setNewPriority] = useState<OrderPriority>('NORMAL')
  const [newDeliveryAt, setNewDeliveryAt] = useState(() =>
    new Date(Date.now() + 6 * 3600_000).toISOString().slice(0, 16),
  )
  const [newNotes, setNewNotes] = useState('')
  const [newItemSku, setNewItemSku] = useState('ELEC-001')
  const [newItemName, setNewItemName] = useState('Industrial Sensor Pack')
  const [newItemQty, setNewItemQty] = useState('2')
  const [newItemPrice, setNewItemPrice] = useState('2500')
  const [newItemWeight, setNewItemWeight] = useState('25')

  const summaryQuery = useQuery({
    queryKey: ['orders', 'summary'],
    queryFn: () => orderService.getSummary(),
    refetchInterval: 15_000,
  })

  const ordersQuery = useQuery({
    queryKey: ['orders', 'list', priorityFilter, statusFilter, overdueOnly, page],
    queryFn: () =>
      orderService.listOrders({
        priority: priorityFilter === 'ALL' ? undefined : priorityFilter,
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        is_overdue: overdueOnly ? true : undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    refetchInterval: 15_000,
  })

  const warehousesQuery = useQuery({
    queryKey: ['warehouses', 'orders-ref'],
    queryFn: () => warehouseService.listWarehouses({ limit: 50 }),
  })

  const vehiclesQuery = useQuery({
    queryKey: ['fleet', 'vehicles', 'orders-ref'],
    queryFn: () => fleetService.listVehicles({ limit: 100 }),
  })

  const customersQuery = useQuery({
    queryKey: ['customers', 'orders-ref'],
    queryFn: () => orderService.listCustomers({ limit: 100 }),
  })

  const orders = ordersQuery.data?.items ?? []

  const visibleOrders = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    if (!q) return orders
    return orders.filter(
      (o) =>
        o.order_number.toLowerCase().includes(q) ||
        o.delivery_address.toLowerCase().includes(q) ||
        (o.customer?.name ?? '').toLowerCase().includes(q),
    )
  }, [orders, searchText])

  const selectedOrder = useMemo(
    () =>
      orders.find((o) => o.id === selectedOrderId) ??
      visibleOrders[0] ??
      orders[0] ??
      null,
    [orders, visibleOrders, selectedOrderId],
  )

  const statusHistoryQuery = useQuery({
    queryKey: ['orders', 'status-history', selectedOrder?.id],
    queryFn: () => orderService.getStatusHistory(selectedOrder!.id),
    enabled: Boolean(selectedOrder?.id),
  })

  const assignHistoryQuery = useQuery({
    queryKey: ['orders', 'assign-history', selectedOrder?.id],
    queryFn: () => orderService.getAssignmentHistory(selectedOrder!.id),
    enabled: Boolean(selectedOrder?.id),
  })

  const assignMutation = useMutation({
    mutationFn: () =>
      orderService.assignVehicle(selectedOrder!.id, {
        vehicle_id: targetVehicleId || null,
        reason: assignReason.trim() || 'Assigned via Order Management console',
      }),
    onSuccess: (updated) => {
      setActionErr(null)
      setActionMsg(`Updated vehicle assignment for ${updated.order_number}.`)
      setAssignModalOpen(false)
      setAssignReason('')
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['fleet'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const statusMutation = useMutation({
    mutationFn: ({ orderId, status }: { orderId: string; status: OrderStatus }) =>
      orderService.updateOrderStatus(orderId, {
        status,
        reason: `Transitioned to ${status} via UI`,
      }),
    onSuccess: (updated) => {
      setActionErr(null)
      setActionMsg(`Order ${updated.order_number} transitioned to ${updated.status}.`)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['fleet'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const createOrderMutation = useMutation({
    mutationFn: () => {
      const cust = (customersQuery.data?.items ?? []).find((c) => c.id === newCustomerId)
      if (!cust) throw new Error('Select a valid customer')
      return orderService.createOrder({
        order_number: newOrderNumber.trim(),
        customer_id: cust.id,
        warehouse_id: newWarehouseId,
        priority: newPriority,
        expected_delivery_at: new Date(newDeliveryAt).toISOString(),
        delivery_address: `${cust.address_line}, ${cust.city}`,
        delivery_latitude: cust.latitude,
        delivery_longitude: cust.longitude,
        notes: newNotes.trim() || undefined,
        items: [
          {
            product_code: newItemSku.trim() || 'ITEM-01',
            product_name: newItemName.trim() || 'Cargo Package',
            quantity: Number(newItemQty) || 1,
            unit_price: Number(newItemPrice) || 100,
            unit_weight_kg: Number(newItemWeight) || 10,
          },
        ],
      })
    },
    onSuccess: (created) => {
      setActionErr(null)
      setActionMsg(`Created order ${created.order_number}.`)
      setCreateModalOpen(false)
      setNewOrderNumber('')
      setSelectedOrderId(created.id)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => setActionErr(getApiErrorMessage(err)),
  })

  const warehouseMap = useMemo(() => {
    const map = new Map<string, NonNullable<typeof warehousesQuery.data>['items'][number]>()
    for (const w of warehousesQuery.data?.items ?? []) {
      map.set(w.id, w)
    }
    return map
  }, [warehousesQuery.data])

  const vehicleMap = useMemo(() => {
    const map = new Map<string, NonNullable<typeof vehiclesQuery.data>['items'][number]>()
    for (const v of vehiclesQuery.data?.items ?? []) {
      map.set(v.id, v)
    }
    return map
  }, [vehiclesQuery.data])

  const allowedTransitions = useMemo(() => {
    if (!selectedOrder) return []
    const base = PERMITTED_ORDER_STATUS_TRANSITIONS[selectedOrder.status as OrderStatus] ?? []
    if (user?.role === 'WAREHOUSE_MANAGER') {
      return base.filter((st) => WAREHOUSE_MANAGER_ALLOWED_STATUSES.includes(st))
    }
    return base
  }, [selectedOrder, user?.role])

  const { previewNodes, previewVehicles, previewPath } = useMemo(() => {
    const nodes: MapNodePoint[] = []
    const vehs: MapVehicleMarker[] = []
    const path: [number, number][] = []
    if (!selectedOrder) return { previewNodes: nodes, previewVehicles: vehs, previewPath: path }

    const originWh = warehouseMap.get(selectedOrder.warehouse_id)
    if (originWh?.network_node) {
      nodes.push({
        id: originWh.id,
        name: `${originWh.warehouse_code} (Origin)`,
        nodeType: 'WAREHOUSE',
        latitude: originWh.network_node.latitude,
        longitude: originWh.network_node.longitude,
      })
      path.push([originWh.network_node.latitude, originWh.network_node.longitude])
    }

    nodes.push({
      id: selectedOrder.id,
      name: `${selectedOrder.order_number} Destination`,
      nodeType: 'CUSTOMER',
      latitude: selectedOrder.delivery_latitude,
      longitude: selectedOrder.delivery_longitude,
      selected: true,
    })
    path.push([selectedOrder.delivery_latitude, selectedOrder.delivery_longitude])

    if (selectedOrder.assigned_vehicle_id) {
      const veh = vehicleMap.get(selectedOrder.assigned_vehicle_id)
      if (veh && veh.current_latitude !== null && veh.current_longitude !== null) {
        vehs.push({
          id: veh.id,
          code: veh.vehicle_code,
          status: veh.status,
          latitude: veh.current_latitude,
          longitude: veh.current_longitude,
          speedKmph: veh.current_speed_kmph,
          selected: true,
        })
      }
    }

    return { previewNodes: nodes, previewVehicles: vehs, previewPath: path }
  }, [selectedOrder, warehouseMap, vehicleMap])

  function handleExportCsv() {
    const header = 'order_number,customer,status,priority,weight_kg,amount,expected_delivery_at\n'
    const rows = visibleOrders
      .map(
        (o) =>
          `${o.order_number},"${o.customer?.name ?? o.customer_id}",${o.status},${o.priority},${o.total_weight_kg},${o.total_amount},${o.expected_delivery_at}`,
      )
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv;charset=utf-8;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'logipulse-orders.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  if (ordersQuery.isLoading || summaryQuery.isLoading) {
    return <LoadingState message="Loading orders directory & fulfillment telemetry..." />
  }

  if (ordersQuery.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(ordersQuery.error)}
        onRetry={() => void ordersQuery.refetch()}
      />
    )
  }

  const summary = summaryQuery.data
  const totalOrdersCount = ordersQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(totalOrdersCount / PAGE_SIZE))

  return (
    <div className="space-y-6">
      {/* Filter Matrix & Action Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
        <div className="flex flex-wrap items-center gap-2">
          {(['ALL', 'URGENT', 'HIGH', 'NORMAL', 'LOW'] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => {
                setPriorityFilter(p)
                setPage(0)
              }}
              className={`rounded px-2.5 py-1 font-telemetry text-xs font-semibold ${priorityFilter === p
                  ? 'bg-primary-fixed text-on-primary-fixed'
                  : 'bg-surface-container text-secondary hover:text-primary'
                }`}
            >
              {p}
            </button>
          ))}

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as 'ALL' | OrderStatus)
              setPage(0)
            }}
            className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-1 text-xs text-primary"
          >
            <option value="ALL">Status: All</option>
            {(Object.keys(PERMITTED_ORDER_STATUS_TRANSITIONS) as OrderStatus[]).map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>

          <label className="flex cursor-pointer items-center gap-1.5 px-2 text-xs text-secondary">
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => {
                setOverdueOnly(e.target.checked)
                setPage(0)
              }}
              className="accent-primary-fixed"
            />
            Overdue only
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Filter current page..."
            className="rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 text-xs text-primary placeholder:text-outline"
          />
          <button
            type="button"
            onClick={handleExportCsv}
            className="inline-flex items-center gap-1.5 rounded border border-surface-container-highest bg-surface-container px-3 py-1.5 font-telemetry text-xs text-primary hover:bg-surface-container-high"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
          {canCreateOrder && (
            <button
              type="button"
              onClick={() => {
                if (!newWarehouseId && warehousesQuery.data?.items[0]) {
                  setNewWarehouseId(warehousesQuery.data.items[0].id)
                }
                if (!newCustomerId && customersQuery.data?.items[0]) {
                  setNewCustomerId(customersQuery.data.items[0].id)
                }
                setCreateModalOpen(true)
              }}
              className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3 py-1.5 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
            >
              <Plus className="h-3.5 w-3.5" />
              Create Order
            </button>
          )}
        </div>
      </div>

      {/* 4 KPI Cards */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Orders"
          value={summary?.total_orders ?? totalOrdersCount}
          sublabel={`${formatNumber(summary?.total_order_weight_kg)} kg cumulative payload`}
          icon={<Package className="h-4 w-4" />}
        />
        <KpiCard
          label="Pending / Ready"
          value={
            (summary?.created_orders ?? 0) +
            (summary?.confirmed_orders ?? 0) +
            (summary?.processing_orders ?? 0) +
            (summary?.ready_for_dispatch_orders ?? 0)
          }
          sublabel={`${summary?.unassigned_orders ?? 0} unassigned to vehicle`}
        />
        <KpiCard
          label="In Transit / Dispatched"
          value={(summary?.in_transit_orders ?? 0) + (summary?.dispatched_orders ?? 0)}
          sublabel={`${summary?.delivered_orders ?? 0} delivered`}
          accent="info"
        />
        <KpiCard
          label="Overdue / Urgent"
          value={summary?.overdue_orders ?? 0}
          sublabel={`${summary?.urgent_orders ?? 0} urgent active consignments`}
          accent={(summary?.overdue_orders ?? 0) > 0 ? 'danger' : 'lime'}
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

      {/* Main Split: Orders Directory (8 cols) + Inspector Drawer (4 cols) */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8 flex flex-col justify-between rounded-lg border border-surface-container-highest bg-surface-container-low p-4">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-surface-container-highest bg-surface-container-lowest font-display text-[11px] uppercase tracking-wider text-outline">
                  <th className="px-3 py-3">Order ID</th>
                  <th className="px-3 py-3">Customer</th>
                  <th className="px-3 py-3">Warehouse</th>
                  <th className="px-3 py-3">Vehicle</th>
                  <th className="px-3 py-3">Priority</th>
                  <th className="px-3 py-3">Exp. Delivery</th>
                  <th className="px-3 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-highest/50">
                {visibleOrders.map((order) => {
                  const wh = warehouseMap.get(order.warehouse_id)
                  const veh = order.assigned_vehicle_id
                    ? vehicleMap.get(order.assigned_vehicle_id)
                    : undefined
                  return (
                    <tr
                      key={order.id}
                      onClick={() => setSelectedOrderId(order.id)}
                      className={`cursor-pointer hover:bg-surface-container ${selectedOrder?.id === order.id ? 'bg-surface-container/80' : ''
                        }`}
                    >
                      <td className="px-3 py-3 font-telemetry font-bold text-lime">
                        {order.order_number}
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-primary">
                          {order.customer?.name ?? 'Customer'}
                        </div>
                        <div className="max-w-[180px] truncate text-[11px] text-outline">
                          {order.delivery_address}
                        </div>
                      </td>
                      <td className="px-3 py-3 font-telemetry text-secondary">
                        {wh?.warehouse_code ?? 'WH'}
                      </td>
                      <td className="px-3 py-3 font-telemetry text-primary">
                        {veh ? veh.vehicle_code : <span className="text-outline">Unassigned</span>}
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge value={order.priority} />
                      </td>
                      <td className="px-3 py-3 font-telemetry text-secondary">
                        {formatDateTimeShort(order.expected_delivery_at)}
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge value={order.status} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {visibleOrders.length === 0 && (
              <EmptyState
                title="No orders match filters"
                description="Reset filters or create a new order."
              />
            )}
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-surface-container-highest pt-3 font-telemetry text-xs text-secondary">
            <span>
              Showing {visibleOrders.length} of {totalOrdersCount} • Page {page + 1} of{' '}
              {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="rounded bg-surface-container px-3 py-1 text-primary disabled:opacity-40"
              >
                Prev
              </button>
              <button
                type="button"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded bg-surface-container px-3 py-1 text-primary disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </div>

        {/* Right: Order Inspector Panel */}
        <div className="lg:col-span-4 rounded-lg border border-surface-container-highest bg-surface-container-low p-4 space-y-4">
          {selectedOrder ? (
            <>
              <div className="border-b border-surface-container-highest pb-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-display text-lg font-bold text-primary">
                    {selectedOrder.order_number}
                  </span>
                  <div className="flex gap-1.5">
                    <StatusBadge value={selectedOrder.priority} />
                    <StatusBadge value={selectedOrder.status} />
                  </div>
                </div>
                <p className="mt-1 text-xs font-medium text-on-surface">
                  {selectedOrder.customer?.name ?? 'Customer'}
                </p>
                <p className="text-[11px] text-secondary">{selectedOrder.delivery_address}</p>
              </div>

              <div className="grid grid-cols-2 gap-2 rounded bg-surface-container p-3 text-xs">
                <div>
                  <span className="text-[10px] uppercase text-outline block">Weight / Amount</span>
                  <span className="font-telemetry font-bold text-primary">
                    {selectedOrder.total_weight_kg} kg • ₹{formatNumber(selectedOrder.total_amount)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase text-outline block">Assigned Vehicle</span>
                  <span className="font-telemetry font-bold text-lime">
                    {selectedOrder.assigned_vehicle_id
                      ? vehicleMap.get(selectedOrder.assigned_vehicle_id)?.vehicle_code ?? 'Assigned'
                      : 'Unassigned'}
                  </span>
                </div>
              </div>

              <BengaluruNetworkMap
                nodes={previewNodes}
                vehicles={previewVehicles}
                highlightedPath={previewPath}
                heightClass="h-[170px]"
              />

              {/* Actions */}
              <div className="space-y-2 border-t border-surface-container-highest pt-3">
                {canAssignVehicle && (
                  <button
                    type="button"
                    disabled={['DELIVERED', 'CANCELLED'].includes(selectedOrder.status)}
                    onClick={() => {
                      setTargetVehicleId(selectedOrder.assigned_vehicle_id ?? '')
                      setAssignModalOpen(true)
                    }}
                    className="flex w-full items-center justify-center gap-2 rounded bg-primary-fixed py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim disabled:opacity-40"
                  >
                    <Truck className="h-3.5 w-3.5" />
                    Assign / Reassign Vehicle
                  </button>
                )}

                {canUpdateStatus && allowedTransitions.length > 0 && (
                  <div className="space-y-1.5">
                    <span className="block font-display text-[10px] font-bold uppercase text-outline">
                      Permitted Status Transitions
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {allowedTransitions.map((nextStatus) => (
                        <button
                          key={nextStatus}
                          type="button"
                          disabled={statusMutation.isPending}
                          onClick={() =>
                            statusMutation.mutate({
                              orderId: selectedOrder.id,
                              status: nextStatus,
                            })
                          }
                          className="rounded border border-surface-container-highest bg-surface-container px-2.5 py-1 font-telemetry text-[11px] font-semibold text-primary hover:border-lime hover:text-lime"
                        >
                          {nextStatus.replace(/_/g, ' ')}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {!canAssignVehicle && !canUpdateStatus && (
                  <UnavailableNotice
                    title="Read-Only Order View"
                    description="Your role does not permit order vehicle assignment or status transitions."
                  />
                )}
              </div>

              {/* Status & Assignment Audit Trail */}
              <div className="space-y-2 border-t border-surface-container-highest pt-3 text-xs">
                <span className="block font-display text-[11px] font-bold uppercase text-outline">
                  Status &amp; Assignment Audit Trail
                </span>
                <div className="max-h-40 space-y-1.5 overflow-y-auto pr-1 font-telemetry text-[11px]">
                  {(statusHistoryQuery.data ?? []).map((h) => (
                    <div key={h.id} className="rounded bg-surface-container p-2 text-secondary">
                      <span className="font-bold text-primary">
                        {h.previous_status ?? 'NEW'} -&gt; {h.new_status}
                      </span>{' '}
                      • {formatDateTimeShort(h.changed_at)}
                      {h.reason && <div className="text-outline">{h.reason}</div>}
                    </div>
                  ))}
                  {(assignHistoryQuery.data ?? []).map((a) => (
                    <div key={a.id} className="rounded bg-surface-container-lowest p-2 text-lime">
                      Vehicle change • {formatDateTimeShort(a.assigned_at)}
                      {a.reason && <div className="text-outline">{a.reason}</div>}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <EmptyState title="No order selected" description="Click any order row to inspect details." />
          )}
        </div>
      </section>

      {/* Assign Vehicle Modal */}
      <Modal
        open={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        title={`Vehicle Assignment — ${selectedOrder?.order_number ?? ''}`}
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            assignMutation.mutate()
          }}
          className="space-y-3 text-xs"
        >
          <p className="text-secondary">
            Order payload: <strong className="text-primary">{selectedOrder?.total_weight_kg} kg</strong>.
            Select an active, non-faulted vehicle with sufficient remaining capacity:
          </p>
          <select
            value={targetVehicleId}
            onChange={(e) => setTargetVehicleId(e.target.value)}
            className="w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
          >
            <option value="">-- Unassign Vehicle --</option>
            {(vehiclesQuery.data?.items ?? [])
              .filter(
                (v) =>
                  v.is_active &&
                  !['BREAKDOWN', 'MAINTENANCE', 'OFFLINE'].includes(v.status),
              )
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.vehicle_code} ({v.status}) — {v.remaining_capacity_kg} kg free / {v.capacity_kg} kg
                </option>
              ))}
          </select>

          <input
            type="text"
            value={assignReason}
            onChange={(e) => setAssignReason(e.target.value)}
            placeholder="Assignment reason..."
            className="w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
          />

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setAssignModalOpen(false)}
              className="rounded bg-surface-container px-4 py-2 text-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={assignMutation.isPending}
              className="rounded bg-primary-fixed px-4 py-2 font-display font-bold text-on-primary-fixed"
            >
              Confirm Assignment
            </button>
          </div>
        </form>
      </Modal>

      {/* Create Order Modal */}
      <Modal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create Consignment Order"
      >
        <form
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            createOrderMutation.mutate()
          }}
          className="space-y-3 text-xs"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Order Number
              </label>
              <input
                required
                value={newOrderNumber}
                onChange={(e) => setNewOrderNumber(e.target.value)}
                placeholder="ORD-BLR-9001"
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              />
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Priority</label>
              <select
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value as OrderPriority)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                <option value="URGENT">URGENT</option>
                <option value="HIGH">HIGH</option>
                <option value="NORMAL">NORMAL</option>
                <option value="LOW">LOW</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">Customer</label>
              <select
                required
                value={newCustomerId}
                onChange={(e) => setNewCustomerId(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                {(customersQuery.data?.items ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.customer_code} — {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-display text-[11px] uppercase text-secondary">
                Origin Warehouse
              </label>
              <select
                required
                value={newWarehouseId}
                onChange={(e) => setNewWarehouseId(e.target.value)}
                className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
              >
                {(warehousesQuery.data?.items ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.warehouse_code}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="font-display text-[11px] uppercase text-secondary">
              Expected Delivery (Local Time -&gt; UTC)
            </label>
            <input
              required
              type="datetime-local"
              value={newDeliveryAt}
              onChange={(e) => setNewDeliveryAt(e.target.value)}
              className="mt-1 w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-2 rounded bg-surface-container p-2.5">
            <input
              value={newItemSku}
              onChange={(e) => setNewItemSku(e.target.value)}
              placeholder="SKU"
              className="rounded border border-surface-container-highest bg-surface-container-lowest px-2 py-1.5 text-primary"
            />
            <input
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              placeholder="Product Name"
              className="rounded border border-surface-container-highest bg-surface-container-lowest px-2 py-1.5 text-primary"
            />
            <input
              type="number"
              min="1"
              value={newItemQty}
              onChange={(e) => setNewItemQty(e.target.value)}
              placeholder="Qty"
              className="rounded border border-surface-container-highest bg-surface-container-lowest px-2 py-1.5 text-primary"
            />
            <input
              type="number"
              min="1"
              value={newItemWeight}
              onChange={(e) => setNewItemWeight(e.target.value)}
              placeholder="Unit Weight kg"
              className="rounded border border-surface-container-highest bg-surface-container-lowest px-2 py-1.5 text-primary"
            />
            <input
              type="number"
              min="0"
              value={newItemPrice}
              onChange={(e) => setNewItemPrice(e.target.value)}
              placeholder="Unit Price"
              className="col-span-2 rounded border border-surface-container-highest bg-surface-container-lowest px-2 py-1.5 text-primary"
            />
          </div>

          <input
            value={newNotes}
            onChange={(e) => setNewNotes(e.target.value)}
            placeholder="Delivery notes (optional)"
            className="w-full rounded border border-surface-container-highest bg-surface-container px-3 py-2 text-primary"
          />

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="rounded bg-surface-container px-4 py-2 text-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createOrderMutation.isPending}
              className="rounded bg-primary-fixed px-4 py-2 font-display font-bold text-on-primary-fixed"
            >
              {createOrderMutation.isPending ? 'Creating...' : 'Create Order'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}


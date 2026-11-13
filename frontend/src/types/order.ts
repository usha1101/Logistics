export type OrderStatus =
  | 'CREATED'
  | 'CONFIRMED'
  | 'PROCESSING'
  | 'READY_FOR_DISPATCH'
  | 'DISPATCHED'
  | 'IN_TRANSIT'
  | 'DELIVERED'
  | 'CANCELLED'
  | 'ON_HOLD'
  | 'FAILED_DELIVERY'

export type OrderPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT'

export const PERMITTED_ORDER_STATUS_TRANSITIONS: Record<OrderStatus, readonly OrderStatus[]> = {
  CREATED: ['CONFIRMED', 'CANCELLED'],
  CONFIRMED: ['PROCESSING', 'ON_HOLD', 'CANCELLED'],
  PROCESSING: ['READY_FOR_DISPATCH', 'ON_HOLD', 'CANCELLED'],
  READY_FOR_DISPATCH: ['DISPATCHED', 'ON_HOLD', 'CANCELLED'],
  DISPATCHED: ['IN_TRANSIT', 'FAILED_DELIVERY'],
  IN_TRANSIT: ['DELIVERED', 'FAILED_DELIVERY'],
  ON_HOLD: ['CONFIRMED', 'PROCESSING', 'CANCELLED'],
  FAILED_DELIVERY: ['PROCESSING', 'ON_HOLD', 'CANCELLED'],
  DELIVERED: [],
  CANCELLED: [],
}

export const WAREHOUSE_MANAGER_ALLOWED_STATUSES: readonly OrderStatus[] = [
  'CONFIRMED',
  'PROCESSING',
  'READY_FOR_DISPATCH',
  'ON_HOLD',
]

export interface CustomerRead {
  id: string
  customer_code: string
  name: string
  email: string | null
  phone: string
  address_line: string
  city: string
  state: string
  postal_code: string
  latitude: number
  longitude: number
  coordinates: [number, number]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CustomerCreate {
  customer_code: string
  name: string
  email?: string
  phone: string
  address_line: string
  city: string
  state: string
  postal_code: string
  latitude: number
  longitude: number
  is_active?: boolean
}

export interface OrderItemCreate {
  product_code: string
  product_name: string
  quantity: number
  unit_price: number
  unit_weight_kg: number
}

export interface OrderItemRead {
  id: string
  order_id: string
  product_code: string
  product_name: string
  quantity: number
  unit_price: number
  unit_weight_kg: number
  subtotal: number
  total_weight_kg: number
  created_at: string
  updated_at: string
}

export interface OrderCreate {
  order_number: string
  customer_id: string
  warehouse_id: string
  priority?: OrderPriority
  expected_delivery_at: string
  delivery_address: string
  delivery_latitude: number
  delivery_longitude: number
  notes?: string
  items?: OrderItemCreate[]
}

export interface OrderUpdate {
  priority?: OrderPriority
  expected_delivery_at?: string
  delivery_address?: string
  delivery_latitude?: number
  delivery_longitude?: number
  notes?: string
}

export interface OrderStatusUpdate {
  status: OrderStatus
  reason?: string
}

export interface OrderAssignmentUpdate {
  vehicle_id: string | null
  reason?: string
}

export interface OrderStatusHistoryRead {
  id: string
  order_id: string
  previous_status: string | null
  new_status: string
  reason: string | null
  changed_by_user_id: string | null
  changed_at: string
}

export interface OrderAssignmentHistoryRead {
  id: string
  order_id: string
  previous_vehicle_id: string | null
  new_vehicle_id: string | null
  assigned_by_user_id: string | null
  reason: string | null
  assigned_at: string
}

export interface OrderRead {
  id: string
  order_number: string
  customer_id: string
  warehouse_id: string
  status: OrderStatus | string
  priority: OrderPriority | string
  order_date: string
  expected_delivery_at: string
  dispatched_at: string | null
  delivered_at: string | null
  delivery_address: string
  delivery_latitude: number
  delivery_longitude: number
  coordinates: [number, number]
  total_weight_kg: number
  total_amount: number
  notes: string | null
  assigned_vehicle_id: string | null
  created_by_user_id: string | null
  is_overdue: boolean
  created_at: string
  updated_at: string
  customer: CustomerRead | null
  items: OrderItemRead[] | null
}

export interface OrderSummaryResponse {
  total_orders: number
  created_orders: number
  confirmed_orders: number
  processing_orders: number
  ready_for_dispatch_orders: number
  dispatched_orders: number
  in_transit_orders: number
  delivered_orders: number
  cancelled_orders: number
  on_hold_orders: number
  failed_delivery_orders: number
  overdue_orders: number
  unassigned_orders: number
  urgent_orders: number
  total_order_value: number
  total_order_weight_kg: number
  generated_at: string
  data_source: string
}


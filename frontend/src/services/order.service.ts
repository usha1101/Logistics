import { apiClient } from '@/lib/api-client'
import type { OffsetPaginatedResponse } from '@/types/common'
import type {
  CustomerCreate,
  CustomerRead,
  OrderAssignmentHistoryRead,
  OrderAssignmentUpdate,
  OrderCreate,
  OrderItemCreate,
  OrderItemRead,
  OrderPriority,
  OrderRead,
  OrderStatus,
  OrderStatusHistoryRead,
  OrderStatusUpdate,
  OrderSummaryResponse,
  OrderUpdate,
} from '@/types/order'

export const orderService = {
  async getSummary(): Promise<OrderSummaryResponse> {
    const { data } = await apiClient.get<OrderSummaryResponse>('/orders/summary')
    return data
  },

  async listOrders(params?: {
    status?: OrderStatus | string
    priority?: OrderPriority | string
    customer_id?: string
    warehouse_id?: string
    assigned_vehicle_id?: string
    is_overdue?: boolean
    start_date?: string
    end_date?: string
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<OrderRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<OrderRead>>('/orders', { params })
    return data
  },

  async getOrder(orderId: string): Promise<OrderRead> {
    const { data } = await apiClient.get<OrderRead>(`/orders/${orderId}`)
    return data
  },

  async createOrder(payload: OrderCreate): Promise<OrderRead> {
    const { data } = await apiClient.post<OrderRead>('/orders', payload)
    return data
  },

  async updateOrder(orderId: string, payload: OrderUpdate): Promise<OrderRead> {
    const { data } = await apiClient.patch<OrderRead>(`/orders/${orderId}`, payload)
    return data
  },

  async updateOrderStatus(orderId: string, payload: OrderStatusUpdate): Promise<OrderRead> {
    const { data } = await apiClient.patch<OrderRead>(`/orders/${orderId}/status`, payload)
    return data
  },

  async assignVehicle(orderId: string, payload: OrderAssignmentUpdate): Promise<OrderRead> {
    const { data } = await apiClient.patch<OrderRead>(`/orders/${orderId}/assignment`, payload)
    return data
  },

  async getStatusHistory(orderId: string): Promise<OrderStatusHistoryRead[]> {
    const { data } = await apiClient.get<OrderStatusHistoryRead[]>(`/orders/${orderId}/history`)
    return data
  },

  async getAssignmentHistory(orderId: string): Promise<OrderAssignmentHistoryRead[]> {
    const { data } = await apiClient.get<OrderAssignmentHistoryRead[]>(
      `/orders/${orderId}/assignment-history`,
    )
    return data
  },

  async addOrderItem(orderId: string, payload: OrderItemCreate): Promise<OrderItemRead> {
    const { data } = await apiClient.post<OrderItemRead>(`/orders/${orderId}/items`, payload)
    return data
  },

  async listCustomers(params?: {
    search?: string
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<CustomerRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<CustomerRead>>('/customers', {
      params,
    })
    return data
  },

  async createCustomer(payload: CustomerCreate): Promise<CustomerRead> {
    const { data } = await apiClient.post<CustomerRead>('/customers', payload)
    return data
  },
}


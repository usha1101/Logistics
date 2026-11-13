import type { UserRole } from '@/types/auth'

export const ROUTE_PERMISSIONS = {
  COMMAND_CENTRE: ['ADMIN', 'OPERATIONS_MANAGER', 'ANALYST'] as readonly UserRole[],
  NETWORK: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  FLEET: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  WAREHOUSES: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  ORDERS: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  SIMULATION: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  AGENTS: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  RECOVERY: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  REPORTS: ['ADMIN', 'OPERATIONS_MANAGER', 'ANALYST'] as readonly UserRole[],
  SETTINGS: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
} as const

export const ACTION_PERMISSIONS = {
  ADMIN_USERS: ['ADMIN'] as readonly UserRole[],
  NETWORK_STATE: ['ADMIN', 'OPERATIONS_MANAGER', 'ANALYST'] as readonly UserRole[],
  WAREHOUSE_SUMMARY: ['ADMIN', 'OPERATIONS_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  WAREHOUSE_MANAGE: ['ADMIN', 'WAREHOUSE_MANAGER'] as readonly UserRole[],
  INVENTORY_MANAGE: ['ADMIN', 'WAREHOUSE_MANAGER'] as readonly UserRole[],
  FLEET_MANAGE: ['ADMIN', 'FLEET_MANAGER'] as readonly UserRole[],
  FLEET_OPERATE: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER'] as readonly UserRole[],
  CUSTOMER_MANAGE: ['ADMIN', 'OPERATIONS_MANAGER'] as readonly UserRole[],
  ORDER_MANAGE: ['ADMIN', 'OPERATIONS_MANAGER'] as readonly UserRole[],
  ORDER_STATUS: ['ADMIN', 'OPERATIONS_MANAGER', 'WAREHOUSE_MANAGER'] as readonly UserRole[],
  ORDER_ASSIGN: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER'] as readonly UserRole[],
  SIMULATION_CONTROL: ['ADMIN', 'OPERATIONS_MANAGER'] as readonly UserRole[],
  DISRUPTION_OPERATE: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER'] as readonly UserRole[],
  AGENT_TRIGGER: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER'] as readonly UserRole[],
  RECOVERY_GENERATE: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'WAREHOUSE_MANAGER'] as readonly UserRole[],
  RECOVERY_DECIDE: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER'] as readonly UserRole[],
  ANALYTICS_FLEET: ['ADMIN', 'OPERATIONS_MANAGER', 'FLEET_MANAGER', 'ANALYST'] as readonly UserRole[],
  ANALYTICS_WAREHOUSE: ['ADMIN', 'OPERATIONS_MANAGER', 'WAREHOUSE_MANAGER', 'ANALYST'] as readonly UserRole[],
  REPORTS_ACCESS: ['ADMIN', 'OPERATIONS_MANAGER', 'ANALYST'] as readonly UserRole[],
} as const

export function hasAnyRole(
  userRole: string | null | undefined,
  allowedRoles: readonly UserRole[],
): boolean {
  if (!userRole) return false
  if (userRole === 'ADMIN') return true
  return allowedRoles.includes(userRole as UserRole)
}

export function getDefaultRouteForRole(userRole: string | null | undefined): string {
  switch (userRole) {
    case 'FLEET_MANAGER':
      return '/fleet'
    case 'WAREHOUSE_MANAGER':
      return '/warehouses'
    case 'ADMIN':
    case 'OPERATIONS_MANAGER':
    case 'ANALYST':
    default:
      return '/command-centre'
  }
}

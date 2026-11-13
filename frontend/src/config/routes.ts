import { ROUTE_PERMISSIONS } from '@/config/permissions'
import type { UserRole } from '@/types/auth'

export interface AppRouteMeta {
  path: string
  label: string
  subtitle: string
  navGroup: 'core' | 'execution' | 'system'
  allowedRoles: readonly UserRole[]
}

export const ROUTES = {
  WELCOME: '/',
  LOGIN: '/login',
  COMMAND_CENTRE: '/command-centre',
  NETWORK: '/network',
  FLEET: '/fleet',
  WAREHOUSES: '/warehouses',
  ORDERS: '/orders',
  SIMULATION: '/simulation',
  AGENTS: '/agents',
  RECOVERY: '/recovery',
  REPORTS: '/reports',
  SETTINGS: '/settings',
} as const

export const SIDEBAR_NAV_ITEMS: readonly AppRouteMeta[] = [
  {
    path: ROUTES.COMMAND_CENTRE,
    label: 'Command Centre',
    subtitle: 'Real-Time Logistics Operations',
    navGroup: 'core',
    allowedRoles: ROUTE_PERMISSIONS.COMMAND_CENTRE,
  },
  {
    path: ROUTES.NETWORK,
    label: 'Network Overview',
    subtitle: 'Spatial Graph & Corridor Topology',
    navGroup: 'core',
    allowedRoles: ROUTE_PERMISSIONS.NETWORK,
  },
  {
    path: ROUTES.FLEET,
    label: 'Fleet Monitoring',
    subtitle: 'Live Vehicle Allocation & Telemetry',
    navGroup: 'core',
    allowedRoles: ROUTE_PERMISSIONS.FLEET,
  },
  {
    path: ROUTES.WAREHOUSES,
    label: 'Warehouse Intelligence',
    subtitle: 'Storage Capacity & Inventory Health',
    navGroup: 'core',
    allowedRoles: ROUTE_PERMISSIONS.WAREHOUSES,
  },
  {
    path: ROUTES.ORDERS,
    label: 'Order Management',
    subtitle: 'Consignment Lifecycle & Dispatch',
    navGroup: 'execution',
    allowedRoles: ROUTE_PERMISSIONS.ORDERS,
  },
  {
    path: ROUTES.SIMULATION,
    label: 'Simulation Studio',
    subtitle: 'Digital Twin Playback & Telemetry',
    navGroup: 'execution',
    allowedRoles: ROUTE_PERMISSIONS.SIMULATION,
  },
  {
    path: ROUTES.AGENTS,
    label: 'AI Agent Control Centre',
    subtitle: 'Multi-Agent Analysis & Consensus',
    navGroup: 'execution',
    allowedRoles: ROUTE_PERMISSIONS.AGENTS,
  },
  {
    path: ROUTES.RECOVERY,
    label: 'Optimization & Recovery',
    subtitle: 'Disruptions & OR-Tools Recovery',
    navGroup: 'execution',
    allowedRoles: ROUTE_PERMISSIONS.RECOVERY,
  },
  {
    path: ROUTES.REPORTS,
    label: 'Reports & Insights',
    subtitle: 'KPI Trends & PDF Export Console',
    navGroup: 'system',
    allowedRoles: ROUTE_PERMISSIONS.REPORTS,
  },
  {
    path: ROUTES.SETTINGS,
    label: 'Settings & Administration',
    subtitle: 'Users, System Health & Preferences',
    navGroup: 'system',
    allowedRoles: ROUTE_PERMISSIONS.SETTINGS,
  },
] as const


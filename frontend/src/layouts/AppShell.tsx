import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BarChart3,
  Bell,
  Clock,
  Cpu,
  FlaskConical,
  LayoutGrid,
  LogOut,
  Menu,
  Network,
  Package,
  Pause,
  Play,
  Route as RouteIcon,
  Settings,
  Square,
  Truck,
  User as UserIcon,
  Warehouse,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'

import { LogiPulseLogo } from '@/components/ui/LogiPulseLogo'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ACTION_PERMISSIONS, hasAnyRole } from '@/config/permissions'
import { ROUTES, SIDEBAR_NAV_ITEMS } from '@/config/routes'
import { formatRoleLabel, getApiErrorMessage } from '@/lib/formatters'
import { disruptionService } from '@/services/disruption.service'
import { simulationService } from '@/services/simulation.service'
import { useAuth } from '@/stores/auth-context'

const ROUTE_ICONS: Record<string, typeof LayoutGrid> = {
  [ROUTES.COMMAND_CENTRE]: LayoutGrid,
  [ROUTES.NETWORK]: Network,
  [ROUTES.FLEET]: Truck,
  [ROUTES.WAREHOUSES]: Warehouse,
  [ROUTES.ORDERS]: Package,
  [ROUTES.SIMULATION]: FlaskConical,
  [ROUTES.AGENTS]: Cpu,
  [ROUTES.RECOVERY]: RouteIcon,
  [ROUTES.REPORTS]: BarChart3,
  [ROUTES.SETTINGS]: Settings,
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [utcTime, setUtcTime] = useState(() => new Date().toISOString().slice(11, 19))
  const [simError, setSimError] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setInterval(() => {
      setUtcTime(new Date().toISOString().slice(11, 19))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  const currentMeta = useMemo(
    () => SIDEBAR_NAV_ITEMS.find((item) => item.path === location.pathname) ?? SIDEBAR_NAV_ITEMS[0],
    [location.pathname],
  )

  const visibleNavItems = useMemo(
    () => SIDEBAR_NAV_ITEMS.filter((item) => hasAnyRole(user?.role, item.allowedRoles)),
    [user?.role],
  )

  const canControlSimulation = hasAnyRole(user?.role, ACTION_PERMISSIONS.SIMULATION_CONTROL)

  const simsQuery = useQuery({
    queryKey: ['simulations', 'header'],
    queryFn: () => simulationService.listSimulations({ limit: 5 }),
    refetchInterval: 10_000,
    enabled: Boolean(user),
  })

  const activeDisruptionsQuery = useQuery({
    queryKey: ['disruptions', 'active-badge'],
    queryFn: () => disruptionService.listActiveDisruptions({ page: 1, page_size: 5 }),
    refetchInterval: 15_000,
    enabled: Boolean(user),
  })

  const activeSimulation = useMemo(() => {
    const items = simsQuery.data?.items ?? []
    return (
      items.find((s) => s.status === 'RUNNING') ??
      items.find((s) => s.status === 'PAUSED') ??
      items[0] ??
      null
    )
  }, [simsQuery.data])

  const simActionMutation = useMutation({
    mutationFn: async (action: 'start' | 'pause' | 'resume' | 'stop') => {
      setSimError(null)
      if (!activeSimulation) {
        if (action === 'start') {
          const created = await simulationService.createSimulation({
            name: 'Bengaluru Operations Twin',
            seed: 42,
            simulation_speed_multiplier: 1,
          })
          return simulationService.start(created.id)
        }
        throw new Error('No simulation run selected or created yet')
      }
      if (action === 'start') {
        if (activeSimulation.status === 'PAUSED') {
          return simulationService.resume(activeSimulation.id)
        }
        if (activeSimulation.status === 'CREATED') {
          return simulationService.start(activeSimulation.id)
        }
        const created = await simulationService.createSimulation({
          name: 'Bengaluru Operations Twin',
          seed: 42,
          simulation_speed_multiplier: 1,
        })
        return simulationService.start(created.id)
      }
      if (action === 'pause') return simulationService.pause(activeSimulation.id)
      if (action === 'resume') return simulationService.resume(activeSimulation.id)
      return simulationService.stop(activeSimulation.id)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['simulations'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => {
      setSimError(getApiErrorMessage(err, 'Simulation action failed'))
    },
  })

  async function handleLogout() {
    await logout()
    navigate(ROUTES.LOGIN, { replace: true })
  }

  const activeDisruptionCount = activeDisruptionsQuery.data?.total ?? 0

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between bg-surface-container-lowest border-r border-surface-container-high/80">
      <div>
        <div className="flex h-16 items-center justify-between px-5 border-b border-surface-container-high/60">
          <Link to={visibleNavItems[0]?.path ?? ROUTES.SETTINGS} className="focus:outline-none">
            <LogiPulseLogo subtitle="Autonomous Platform" />
          </Link>
          <button
            type="button"
            onClick={() => setMobileNavOpen(false)}
            className="rounded p-1 text-secondary hover:text-primary lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="mt-4 px-3 space-y-1" aria-label="Main navigation">
          {visibleNavItems.map((item) => {
            const Icon = ROUTE_ICONS[item.path] ?? LayoutGrid
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-primary-fixed text-on-primary-fixed font-display font-semibold shadow-[0_0_14px_rgba(198,244,50,0.28)]'
                      : 'text-secondary hover:bg-surface-container hover:text-primary'
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            )
          })}
        </nav>
      </div>

      <div className="border-t border-surface-container-high/60 p-4 space-y-3">
        <div className="rounded-md bg-surface-container p-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-fixed/15 text-primary-fixed border border-primary-fixed/30">
              <UserIcon className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-primary">
                {user?.full_name || user?.username || 'Operator'}
              </div>
              <div className="truncate font-telemetry text-[10px] uppercase tracking-wider text-lime">
                {formatRoleLabel(user?.role)}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            title="Sign out"
            className="rounded p-1.5 text-secondary hover:bg-surface-container-high hover:text-[#F87171] transition-colors"
            aria-label="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-canvas text-on-surface">
      {/* Desktop Fixed Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 lg:block">{sidebarContent}</aside>

      {/* Mobile Drawer Sidebar */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-xs"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="relative z-10 h-full w-72">{sidebarContent}</aside>
        </div>
      )}

      {/* Main Content Wrapper */}
      <div className="lg:pl-72 flex min-h-screen flex-col">
        {/* Global Fixed-Feel Sticky Header */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-surface-container-high/70 bg-surface-container-lowest/95 px-4 sm:px-6 backdrop-blur-xl">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              className="rounded p-1.5 text-secondary hover:bg-surface-container hover:text-primary lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate font-display text-base font-bold tracking-tight text-primary">
                {currentMeta.label}
              </h1>
              <p className="hidden sm:block truncate text-[11px] text-secondary">
                {currentMeta.subtitle}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Simulation Live Status & Controls */}
            <div className="hidden md:flex items-center gap-2 rounded-md border border-surface-container-highest bg-surface-container-low px-2.5 py-1">
              <StatusBadge
                value={activeSimulation ? `SIM: ${activeSimulation.status}` : 'SIM: IDLE'}
                tone={activeSimulation?.status === 'RUNNING' ? 'lime' : 'neutral'}
                pulse={activeSimulation?.status === 'RUNNING'}
              />
              {canControlSimulation && (
                <div className="flex items-center gap-1 border-l border-surface-container-highest pl-2">
                  <button
                    type="button"
                    disabled={simActionMutation.isPending || activeSimulation?.status === 'RUNNING'}
                    onClick={() => simActionMutation.mutate('start')}
                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-display font-semibold text-primary-fixed hover:bg-primary-fixed/15 disabled:opacity-40"
                    title="Start or resume simulation"
                  >
                    <Play className="h-3 w-3" />
                    <span className="hidden xl:inline">Start</span>
                  </button>
                  <button
                    type="button"
                    disabled={simActionMutation.isPending || activeSimulation?.status !== 'RUNNING'}
                    onClick={() => simActionMutation.mutate('pause')}
                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-display font-semibold text-secondary hover:bg-surface-container hover:text-primary disabled:opacity-40"
                    title="Pause simulation"
                  >
                    <Pause className="h-3 w-3" />
                    <span className="hidden xl:inline">Pause</span>
                  </button>
                  <button
                    type="button"
                    disabled={
                      simActionMutation.isPending ||
                      !activeSimulation ||
                      !['RUNNING', 'PAUSED'].includes(activeSimulation.status)
                    }
                    onClick={() => simActionMutation.mutate('stop')}
                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-display font-semibold text-error hover:bg-[#EF4444]/15 disabled:opacity-40"
                    title="Stop simulation"
                  >
                    <Square className="h-3 w-3" />
                    <span className="hidden xl:inline">Stop</span>
                  </button>
                </div>
              )}
            </div>

            {/* UTC Clock */}
            <div className="hidden sm:flex items-center gap-1.5 rounded bg-surface-container px-2.5 py-1 font-telemetry text-xs text-secondary">
              <Clock className="h-3.5 w-3.5 text-lime" />
              <span>{utcTime} UTC</span>
            </div>

            {/* Active Disruptions Alert Bell */}
            <Link
              to={ROUTES.RECOVERY}
              className="relative flex h-9 w-9 items-center justify-center rounded-md border border-surface-container-highest bg-surface-container-low text-secondary hover:border-lime/50 hover:text-primary transition-colors"
              title="View active disruptions & recovery"
            >
              <Bell className="h-4 w-4" />
              {activeDisruptionCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-[#EF4444] px-1 font-telemetry text-[10px] font-bold text-white">
                  {activeDisruptionCount}
                </span>
              )}
            </Link>
          </div>
        </header>

        {simError && (
          <div className="mx-6 mt-3 flex items-center justify-between rounded border border-[#EF4444]/40 bg-[#93000a]/25 px-3 py-2 text-xs text-error">
            <span>{simError}</span>
            <button type="button" onClick={() => setSimError(null)} className="underline">
              Dismiss
            </button>
          </div>
        )}

        <main className="flex-1 p-4 sm:p-6 space-y-6">{children}</main>
      </div>
    </div>
  )
}


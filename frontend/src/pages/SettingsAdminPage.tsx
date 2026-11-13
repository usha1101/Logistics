import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  Bot,
  Check,
  Database,
  FileText,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Server,
  Shield,
  Sliders,
  User as UserIcon,
  Users,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  RestrictedBanner,
  UnavailableNotice,
} from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ACTION_PERMISSIONS, ROUTE_PERMISSIONS, hasAnyRole } from '@/config/permissions'
import { formatDateTimeShort, formatRoleLabel, getApiErrorMessage } from '@/lib/formatters'
import { agentService } from '@/services/agent.service'
import { analyticsService } from '@/services/analytics.service'
import { authService } from '@/services/auth.service'
import { useAuth } from '@/stores/auth-context'
import { USER_ROLES, type UserCreate, type UserRead, type UserRole } from '@/types/auth'

type SettingsTab = 'profile' | 'users' | 'diagnostics' | 'rbac'

const UI_PREFS_KEY = 'logipulse_ui_prefs'

interface LocalUiPrefs {
  timeDisplay: 'UTC' | 'LOCAL'
  compactTables: boolean
}

function loadLocalPrefs(): LocalUiPrefs {
  try {
    const raw = window.localStorage.getItem(UI_PREFS_KEY)
    if (!raw) return { timeDisplay: 'UTC', compactTables: false }
    const parsed = JSON.parse(raw) as Partial<LocalUiPrefs>
    return {
      timeDisplay: parsed.timeDisplay === 'LOCAL' ? 'LOCAL' : 'UTC',
      compactTables: Boolean(parsed.compactTables),
    }
  } catch {
    return { timeDisplay: 'UTC', compactTables: false }
  }
}

const RBAC_MATRIX_ROWS: Array<{
  capability: string
  roles: readonly UserRole[]
}> = [
  { capability: 'Dashboard & Executive Command Centre', roles: ROUTE_PERMISSIONS.COMMAND_CENTRE },
  { capability: 'Network Topology & Simulation Map View', roles: ROUTE_PERMISSIONS.NETWORK },
  { capability: 'Analytics & PDF Reports (`/analytics/*`, `/reports/*`)', roles: ACTION_PERMISSIONS.REPORTS_ACCESS },
  { capability: 'User Management & Role Assignment (`/admin/users`, `/auth/register`)', roles: ACTION_PERMISSIONS.ADMIN_USERS },
  { capability: 'Simulation Start / Pause / Stop / Step', roles: ACTION_PERMISSIONS.SIMULATION_CONTROL },
  { capability: 'Order Creation & Customer Management', roles: ACTION_PERMISSIONS.ORDER_MANAGE },
  { capability: 'Vehicle Assignment & Fleet Operations', roles: ACTION_PERMISSIONS.ORDER_ASSIGN },
  { capability: 'Fleet Master Create / Update / Delete', roles: ACTION_PERMISSIONS.FLEET_MANAGE },
  { capability: 'Warehouse & Inventory Master Management', roles: ACTION_PERMISSIONS.WAREHOUSE_MANAGE },
  { capability: 'Disruption Reporting & AI Agent Triggering', roles: ACTION_PERMISSIONS.AGENT_TRIGGER },
  { capability: 'Recovery Plan Approval / Rejection / Execution', roles: ACTION_PERMISSIONS.RECOVERY_DECIDE },
]

export function SettingsAdminPage() {
  const { user, refreshMe } = useAuth()
  const queryClient = useQueryClient()

  const isAdmin = hasAnyRole(user?.role, ACTION_PERMISSIONS.ADMIN_USERS)
  const canReadAnalyticsHealth = hasAnyRole(user?.role, ROUTE_PERMISSIONS.REPORTS)

  const [activeTab, setActiveTab] = useState<SettingsTab>('profile')
  const [userSearch, setUserSearch] = useState('')
  const [createUserOpen, setCreateUserOpen] = useState(false)
  const [formState, setFormState] = useState<UserCreate>({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'OPERATIONS_MANAGER',
  })
  const [actionFeedback, setActionFeedback] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null)
  const [refreshingProfile, setRefreshingProfile] = useState(false)
  const [uiPrefs, setUiPrefs] = useState<LocalUiPrefs>(() => loadLocalPrefs())

  const systemHealthQuery = useQuery({
    queryKey: ['system', 'health'],
    queryFn: () => analyticsService.getSystemHealth(),
  })

  const agentStatusQuery = useQuery({
    queryKey: ['agents', 'status'],
    queryFn: () => agentService.getProviderStatus(),
  })

  const analyticsHealthQuery = useQuery({
    queryKey: ['analytics', 'health'],
    queryFn: () => analyticsService.getAnalyticsHealth(),
    enabled: canReadAnalyticsHealth,
  })

  const adminUsersQuery = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => authService.listAdminUsers(),
    enabled: isAdmin,
  })

  const createUserMutation = useMutation({
    mutationFn: (payload: UserCreate) => authService.registerUser(payload),
    onSuccess: (created) => {
      setActionFeedback({
        type: 'success',
        message: `Provisioned user ${created.username} (${formatRoleLabel(created.role)})`,
      })
      setCreateUserOpen(false)
      setFormState({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'OPERATIONS_MANAGER',
      })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (err) => {
      setActionFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to register user'),
      })
    },
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      authService.updateUserRole(userId, role),
    onSuccess: (updated) => {
      setUpdatingUserId(null)
      setActionFeedback({
        type: 'success',
        message: `Updated ${updated.username} role to ${formatRoleLabel(updated.role)}`,
      })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      if (updated.id === user?.id) {
        void refreshMe()
      }
    },
    onError: (err) => {
      setUpdatingUserId(null)
      setActionFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to update user role'),
      })
    },
  })

  const filteredUsers = useMemo(() => {
    const items = adminUsersQuery.data ?? []
    const q = userSearch.trim().toLowerCase()
    if (!q) return items
    return items.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.role.toLowerCase().includes(q),
    )
  }, [adminUsersQuery.data, userSearch])

  const handleRefreshProfile = async () => {
    setRefreshingProfile(true)
    setActionFeedback(null)
    try {
      await refreshMe()
      setActionFeedback({
        type: 'success',
        message: 'Verified session and refreshed user claims from GET /auth/me',
      })
    } finally {
      setRefreshingProfile(false)
    }
  }

  const handleRoleChange = (targetUser: UserRead, newRole: UserRole) => {
    if (targetUser.role === newRole) return
    setActionFeedback(null)
    setUpdatingUserId(targetUser.id)
    updateRoleMutation.mutate({ userId: targetUser.id, role: newRole })
  }

  const handleCreateUserSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setActionFeedback(null)
    createUserMutation.mutate(formState)
  }

  const updateLocalPrefs = (patch: Partial<LocalUiPrefs>) => {
    const next = { ...uiPrefs, ...patch }
    setUiPrefs(next)
    try {
      window.localStorage.setItem(UI_PREFS_KEY, JSON.stringify(next))
    } catch {
      // Ignore storage quota issues in restricted browsers
    }
  }

  return (
    <div className="space-y-6">
      {/* Section Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-container-highest pb-3">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('profile')}
            className={`inline-flex items-center gap-2 rounded-md px-3.5 py-2 font-display text-xs font-semibold transition-colors ${
              activeTab === 'profile'
                ? 'bg-primary-fixed text-on-primary-fixed'
                : 'bg-surface-container text-secondary hover:text-primary'
            }`}
          >
            <UserIcon className="h-3.5 w-3.5" />
            Session & Preferences
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('users')}
            className={`inline-flex items-center gap-2 rounded-md px-3.5 py-2 font-display text-xs font-semibold transition-colors ${
              activeTab === 'users'
                ? 'bg-primary-fixed text-on-primary-fixed'
                : 'bg-surface-container text-secondary hover:text-primary'
            }`}
          >
            <Users className="h-3.5 w-3.5" />
            User Management
            {!isAdmin && (
              <span className="rounded bg-black/30 px-1.5 py-0.5 font-telemetry text-[10px]">
                ADMIN ONLY
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('diagnostics')}
            className={`inline-flex items-center gap-2 rounded-md px-3.5 py-2 font-display text-xs font-semibold transition-colors ${
              activeTab === 'diagnostics'
                ? 'bg-primary-fixed text-on-primary-fixed'
                : 'bg-surface-container text-secondary hover:text-primary'
            }`}
          >
            <Server className="h-3.5 w-3.5" />
            Backend Diagnostics
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('rbac')}
            className={`inline-flex items-center gap-2 rounded-md px-3.5 py-2 font-display text-xs font-semibold transition-colors ${
              activeTab === 'rbac'
                ? 'bg-primary-fixed text-on-primary-fixed'
                : 'bg-surface-container text-secondary hover:text-primary'
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            RBAC Matrix
          </button>
        </div>

        <div className="flex items-center gap-2 font-telemetry text-xs text-secondary">
          <span>Active Role:</span>
          <StatusBadge value={user?.role} tone="lime" />
        </div>
      </div>

      {actionFeedback && (
        <div
          className={`rounded-lg border px-4 py-3 text-xs ${
            actionFeedback.type === 'success'
              ? 'border-[#22C55E]/40 bg-[#22C55E]/10 text-[#22C55E]'
              : 'border-[#EF4444]/40 bg-[#93000a]/20 text-error'
          }`}
        >
          {actionFeedback.message}
        </div>
      )}

      {/* TAB 1: Profile, Account Security Disclosure & Browser-Local Preferences */}
      {activeTab === 'profile' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-4">
            <div className="flex items-center justify-between gap-2 border-b border-surface-container-highest pb-3">
              <div className="flex items-center gap-2">
                <UserIcon className="h-4 w-4 text-lime" />
                <h2 className="font-display text-sm font-bold text-primary">
                  Authenticated Operator Session (`GET /auth/me`)
                </h2>
              </div>
              <button
                type="button"
                onClick={() => void handleRefreshProfile()}
                disabled={refreshingProfile}
                className="inline-flex items-center gap-1.5 rounded border border-outline-variant bg-surface-container px-2.5 py-1.5 font-display text-xs font-semibold text-primary hover:bg-surface-container-high disabled:opacity-50"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${refreshingProfile ? 'animate-spin' : ''}`}
                />
                Verify Session
              </button>
            </div>

            {user ? (
              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-xs">
                <div className="rounded border border-surface-container-highest bg-surface-container p-3">
                  <dt className="font-telemetry text-[10px] uppercase tracking-wider text-outline">
                    Full Name
                  </dt>
                  <dd className="mt-1 font-semibold text-primary">{user.full_name}</dd>
                </div>
                <div className="rounded border border-surface-container-highest bg-surface-container p-3">
                  <dt className="font-telemetry text-[10px] uppercase tracking-wider text-outline">
                    Username
                  </dt>
                  <dd className="mt-1 font-telemetry text-primary">@{user.username}</dd>
                </div>
                <div className="rounded border border-surface-container-highest bg-surface-container p-3">
                  <dt className="font-telemetry text-[10px] uppercase tracking-wider text-outline">
                    Email Address
                  </dt>
                  <dd className="mt-1 text-secondary">{user.email}</dd>
                </div>
                <div className="rounded border border-surface-container-highest bg-surface-container p-3">
                  <dt className="font-telemetry text-[10px] uppercase tracking-wider text-outline">
                    Assigned Backend Role
                  </dt>
                  <dd className="mt-1">
                    <StatusBadge value={user.role} tone="lime" />
                  </dd>
                </div>
                <div className="rounded border border-surface-container-highest bg-surface-container p-3">
                  <dt className="font-telemetry text-[10px] uppercase tracking-wider text-outline">
                    Account Status
                  </dt>
                  <dd className="mt-1">
                    <StatusBadge
                      value={user.is_active ? 'ACTIVE' : 'INACTIVE'}
                      tone={user.is_active ? 'success' : 'danger'}
                    />
                  </dd>
                </div>
                <div className="rounded border border-surface-container-highest bg-surface-container p-3">
                  <dt className="font-telemetry text-[10px] uppercase tracking-wider text-outline">
                    Last Updated
                  </dt>
                  <dd className="mt-1 font-telemetry text-secondary">
                    {formatDateTimeShort(user.updated_at)}
                  </dd>
                </div>
              </dl>
            ) : (
              <LoadingState message="Loading authenticated profile..." />
            )}

            <UnavailableNotice
              title="Self-Service Password Change & 2FA Not Supported by Backend"
              description="The FastAPI `/auth` router supports JWT login, session inspection, and admin user registration (`/auth/register`), without self-service password reset or 2FA endpoints."
            />
          </section>

          <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-surface-container-highest pb-3">
              <Sliders className="h-4 w-4 text-lime" />
              <h2 className="font-display text-sm font-bold text-primary">
                Operator Display Preferences (Browser-Local)
              </h2>
            </div>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between gap-4 rounded border border-surface-container-highest bg-surface-container p-3.5">
                <div>
                  <div className="font-semibold text-primary">Clock Reference</div>
                  <div className="mt-0.5 text-secondary">
                    Display timestamps in UTC telemetry or browser local time
                  </div>
                </div>
                <div className="flex rounded border border-outline-variant p-0.5 bg-surface-container-low">
                  {(['UTC', 'LOCAL'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => updateLocalPrefs({ timeDisplay: mode })}
                      className={`rounded px-2.5 py-1 font-telemetry text-[11px] font-semibold ${
                        uiPrefs.timeDisplay === mode
                          ? 'bg-primary-fixed text-on-primary-fixed'
                          : 'text-secondary hover:text-primary'
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              <label className="flex cursor-pointer items-center justify-between gap-4 rounded border border-surface-container-highest bg-surface-container p-3.5">
                <div>
                  <div className="font-semibold text-primary">Compact Table Spacing</div>
                  <div className="mt-0.5 text-secondary">
                    Stored in browser `localStorage` only (`logipulse_ui_prefs`)
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={uiPrefs.compactTables}
                  onChange={(e) => updateLocalPrefs({ compactTables: e.target.checked })}
                  className="h-4 w-4 accent-[#c5f331]"
                />
              </label>

              <UnavailableNotice
                title="External Platform Integrations Not Configurable via API"
                description="Stitch design panels for Kafka brokers, SAP S/4HANA ERP sync, Mapbox keys, and TimescaleDB retention are omitted as controls because the backend does not expose external integration settings endpoints."
              />
            </div>
          </section>
        </div>
      )}

      {/* TAB 2: Admin User Management */}
      {activeTab === 'users' && (
        <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-4">
          {!isAdmin ? (
            <RestrictedBanner message="Access restricted: Backend endpoints `GET /admin/users`, `POST /auth/register`, and `PATCH /admin/users/{id}/role` require the ADMIN role." />
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-display text-sm font-bold text-primary">
                    User Provisioning & Role Assignment
                  </h2>
                  <p className="text-xs text-secondary">
                    Manage active logistics operators (`GET /admin/users` • `POST /auth/register` • `PATCH /admin/users/:id/role`)
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-outline" />
                    <input
                      type="text"
                      value={userSearch}
                      onChange={(e) => setUserSearch(e.target.value)}
                      placeholder="Filter username, email, role..."
                      className="rounded border border-outline-variant bg-surface-container py-1.5 pl-8 pr-3 text-xs text-primary placeholder:text-outline focus:border-lime focus:outline-none"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => setCreateUserOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3.5 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Provision User
                  </button>
                </div>
              </div>

              {adminUsersQuery.isLoading ? (
                <LoadingState message="Loading backend user registry..." />
              ) : adminUsersQuery.isError ? (
                <ErrorState
                  message={getApiErrorMessage(adminUsersQuery.error)}
                  onRetry={() => void adminUsersQuery.refetch()}
                />
              ) : filteredUsers.length === 0 ? (
                <EmptyState
                  title="No Matching Users"
                  description="No user accounts match the current search filter."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-surface-container-highest bg-surface-container/60 font-telemetry text-[11px] uppercase tracking-wider text-outline">
                      <tr>
                        <th className="px-4 py-2.5">Operator</th>
                        <th className="px-4 py-2.5">Email</th>
                        <th className="px-4 py-2.5">Status</th>
                        <th className="px-4 py-2.5">Created</th>
                        <th className="px-4 py-2.5">Role Assignment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-container-highest/50">
                      {filteredUsers.map((u) => (
                        <tr key={u.id} className="hover:bg-surface-container/40">
                          <td className="px-4 py-3">
                            <div className="font-semibold text-primary">
                              {u.full_name}
                              {u.id === user?.id && (
                                <span className="ml-2 rounded bg-primary-fixed/15 px-1.5 py-0.5 font-telemetry text-[10px] text-lime">
                                  YOU
                                </span>
                              )}
                            </div>
                            <div className="font-telemetry text-[11px] text-outline">
                              @{u.username}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-secondary">{u.email}</td>
                          <td className="px-4 py-3">
                            <StatusBadge
                              value={u.is_active ? 'ACTIVE' : 'INACTIVE'}
                              tone={u.is_active ? 'success' : 'danger'}
                            />
                          </td>
                          <td className="px-4 py-3 font-telemetry text-secondary">
                            {formatDateTimeShort(u.created_at)}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <select
                                value={u.role}
                                disabled={updatingUserId === u.id}
                                onChange={(e) =>
                                  handleRoleChange(u, e.target.value as UserRole)
                                }
                                className="rounded border border-outline-variant bg-surface-container px-2.5 py-1.5 font-telemetry text-xs text-primary focus:border-lime focus:outline-none disabled:opacity-50"
                              >
                                {USER_ROLES.map((roleOpt) => (
                                  <option key={roleOpt} value={roleOpt}>
                                    {roleOpt}
                                  </option>
                                ))}
                              </select>
                              {updatingUserId === u.id && (
                                <Loader2 className="h-3.5 w-3.5 animate-spin text-lime" />
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* TAB 3: Live Backend Service Health & AI Provider Status */}
      {activeTab === 'diagnostics' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Core Backend Health */}
          <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-surface-container-highest pb-2.5">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-lime" />
                <h2 className="font-display text-sm font-bold text-primary">
                  Core API & Database
                </h2>
              </div>
              {systemHealthQuery.data && (
                <StatusBadge
                  value={systemHealthQuery.data.status.toUpperCase()}
                  tone={systemHealthQuery.data.database.connected ? 'success' : 'danger'}
                />
              )}
            </div>
            {systemHealthQuery.isLoading ? (
              <LoadingState message="Checking /health..." />
            ) : systemHealthQuery.isError ? (
              <ErrorState
                message={getApiErrorMessage(systemHealthQuery.error)}
                onRetry={() => void systemHealthQuery.refetch()}
              />
            ) : systemHealthQuery.data ? (
              <dl className="space-y-2 font-telemetry text-xs">
                <div className="flex justify-between">
                  <dt className="text-outline">Application</dt>
                  <dd className="text-primary">
                    {systemHealthQuery.data.app} v{systemHealthQuery.data.version}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Environment</dt>
                  <dd className="text-secondary">{systemHealthQuery.data.environment}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">DB Connection</dt>
                  <dd
                    className={
                      systemHealthQuery.data.database.connected
                        ? 'text-[#22C55E]'
                        : 'text-[#F87171]'
                    }
                  >
                    {systemHealthQuery.data.database.connected ? 'CONNECTED' : 'DISCONNECTED'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Data Source Mode</dt>
                  <dd className="text-lime">{systemHealthQuery.data.data_source}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Server UTC</dt>
                  <dd className="text-secondary">
                    {formatDateTimeShort(systemHealthQuery.data.server_time_utc)}
                  </dd>
                </div>
              </dl>
            ) : null}
          </section>

          {/* AI Provider Diagnostics */}
          <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-surface-container-highest pb-2.5">
              <div className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-lime" />
                <h2 className="font-display text-sm font-bold text-primary">
                  LLM Provider Status
                </h2>
              </div>
              {agentStatusQuery.data && (
                <StatusBadge
                  value={
                    agentStatusQuery.data.gemini_configured ||
                    agentStatusQuery.data.groq_configured
                      ? 'ACTIVE'
                      : 'AI_UNAVAILABLE'
                  }
                />
              )}
            </div>
            {agentStatusQuery.isLoading ? (
              <LoadingState message="Checking /agents/status..." />
            ) : agentStatusQuery.isError ? (
              <ErrorState
                message={getApiErrorMessage(agentStatusQuery.error)}
                onRetry={() => void agentStatusQuery.refetch()}
              />
            ) : agentStatusQuery.data ? (
              <dl className="space-y-2 font-telemetry text-xs">
                <div className="flex justify-between">
                  <dt className="text-outline">Primary Provider</dt>
                  <dd className="text-primary">{agentStatusQuery.data.primary_provider}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Primary Model</dt>
                  <dd className="truncate max-w-[180px] text-lime">
                    {agentStatusQuery.data.primary_model}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Fallback Provider</dt>
                  <dd className="text-primary">{agentStatusQuery.data.fallback_provider}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Fallback Model</dt>
                  <dd className="truncate max-w-[180px] text-secondary">
                    {agentStatusQuery.data.fallback_model}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Gemini / Groq Configured</dt>
                  <dd className="text-primary">
                    {agentStatusQuery.data.gemini_configured ? 'YES' : 'NO'} /{' '}
                    {agentStatusQuery.data.groq_configured ? 'YES' : 'NO'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Timeout / Retries</dt>
                  <dd className="text-secondary">
                    {agentStatusQuery.data.timeout_seconds}s / {agentStatusQuery.data.max_retries}
                  </dd>
                </div>
              </dl>
            ) : null}
          </section>

          {/* Analytics & PDF Engine Health */}
          <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-surface-container-highest pb-2.5">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-lime" />
                <h2 className="font-display text-sm font-bold text-primary">
                  Analytics & PDF Engine
                </h2>
              </div>
              {analyticsHealthQuery.data && (
                <StatusBadge
                  value={analyticsHealthQuery.data.status.toUpperCase()}
                  tone={analyticsHealthQuery.data.reportlab_available ? 'success' : 'warn'}
                />
              )}
            </div>
            {!canReadAnalyticsHealth ? (
              <RestrictedBanner message="Analytics health (`/analytics/health`) is restricted to ADMIN, OPERATIONS_MANAGER, and ANALYST roles." />
            ) : analyticsHealthQuery.isLoading ? (
              <LoadingState message="Checking /analytics/health..." />
            ) : analyticsHealthQuery.isError ? (
              <ErrorState
                message={getApiErrorMessage(analyticsHealthQuery.error)}
                onRetry={() => void analyticsHealthQuery.refetch()}
              />
            ) : analyticsHealthQuery.data ? (
              <dl className="space-y-2 font-telemetry text-xs">
                <div className="flex justify-between">
                  <dt className="text-outline">Analytics Engine</dt>
                  <dd className="text-primary">{analyticsHealthQuery.data.analytics_engine}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">PDF Engine</dt>
                  <dd className="text-primary">{analyticsHealthQuery.data.pdf_reporting_engine}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">ReportLab Available</dt>
                  <dd
                    className={
                      analyticsHealthQuery.data.reportlab_available
                        ? 'text-[#22C55E]'
                        : 'text-[#F87171]'
                    }
                  >
                    {analyticsHealthQuery.data.reportlab_available ? 'READY' : 'MISSING'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Reports Storage</dt>
                  <dd className="text-secondary">
                    {analyticsHealthQuery.data.reports_storage_ready ? 'WRITABLE' : 'UNAVAILABLE'}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-outline">Total Reports Generated</dt>
                  <dd className="text-lime">{analyticsHealthQuery.data.total_generated_reports}</dd>
                </div>
              </dl>
            ) : null}
          </section>
        </div>
      )}

      {/* TAB 4: Backend RBAC Reference Matrix */}
      {activeTab === 'rbac' && (
        <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-lime" />
              <div>
                <h2 className="font-display text-sm font-bold text-primary">
                  Enforced Backend Role Permissions (Read-Only)
                </h2>
                <p className="text-xs text-secondary">
                  Mirrors FastAPI `require_roles(...)` dependencies (`ADMIN` is authorized across all endpoints). Role policies cannot be edited at runtime.
                </p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-surface-container-highest bg-surface-container/60 font-telemetry text-[11px] uppercase tracking-wider text-outline">
                <tr>
                  <th className="px-4 py-2.5">Backend Capability</th>
                  {USER_ROLES.map((role) => (
                    <th key={role} className="px-3 py-2.5 text-center">
                      {role.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-highest/50">
                {RBAC_MATRIX_ROWS.map((row) => (
                  <tr key={row.capability} className="hover:bg-surface-container/40">
                    <td className="px-4 py-2.5 font-medium text-primary">{row.capability}</td>
                    {USER_ROLES.map((role) => {
                      const allowed = role === 'ADMIN' || row.roles.includes(role)
                      return (
                        <td key={role} className="px-3 py-2.5 text-center">
                          {allowed ? (
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary-fixed/15 text-lime">
                              <Check className="h-3.5 w-3.5" />
                            </span>
                          ) : (
                            <span className="font-telemetry text-outline">—</span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Provision User Modal (`POST /auth/register`) */}
      <Modal
        open={createUserOpen}
        onClose={() => setCreateUserOpen(false)}
        title="Provision New Backend User (`POST /auth/register`)"
      >
        <form onSubmit={handleCreateUserSubmit} className="space-y-3.5 text-xs">
          <div>
            <label className="mb-1 block font-telemetry text-[11px] uppercase tracking-wider text-outline">
              Full Name
            </label>
            <input
              type="text"
              required
              minLength={2}
              value={formState.full_name}
              onChange={(e) => setFormState((s) => ({ ...s, full_name: e.target.value }))}
              placeholder="e.g. Arjun Nair"
              className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 text-xs text-primary focus:border-lime focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block font-telemetry text-[11px] uppercase tracking-wider text-outline">
                Username
              </label>
              <input
                type="text"
                required
                minLength={3}
                value={formState.username}
                onChange={(e) => setFormState((s) => ({ ...s, username: e.target.value }))}
                placeholder="arjun_ops"
                className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 font-telemetry text-xs text-primary focus:border-lime focus:outline-none"
              />
            </div>

            <div>
              <label className="mb-1 block font-telemetry text-[11px] uppercase tracking-wider text-outline">
                Role
              </label>
              <select
                value={formState.role}
                onChange={(e) =>
                  setFormState((s) => ({ ...s, role: e.target.value as UserRole }))
                }
                className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 font-telemetry text-xs text-primary focus:border-lime focus:outline-none"
              >
                {USER_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block font-telemetry text-[11px] uppercase tracking-wider text-outline">
              Email Address
            </label>
            <input
              type="email"
              required
              value={formState.email}
              onChange={(e) => setFormState((s) => ({ ...s, email: e.target.value }))}
              placeholder="arjun.nair@logipulse.in"
              className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 text-xs text-primary focus:border-lime focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 flex items-center gap-1.5 font-telemetry text-[11px] uppercase tracking-wider text-outline">
              <KeyRound className="h-3 w-3" />
              Initial Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              maxLength={128}
              value={formState.password}
              onChange={(e) => setFormState((s) => ({ ...s, password: e.target.value }))}
              placeholder="Minimum 8 characters with letters and digits"
              className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 text-xs text-primary focus:border-lime focus:outline-none"
            />
            <p className="mt-1 text-[11px] text-secondary">
              Backend enforces 8–128 characters containing at least one letter and one digit.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setCreateUserOpen(false)}
              className="rounded border border-outline-variant px-4 py-2 font-display text-xs font-semibold text-secondary hover:text-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createUserMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-4 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim disabled:opacity-60"
            >
              {createUserMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create Account
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}


import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  ChevronDown,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  ShieldCheck,
} from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { LogiPulseLogo } from '@/components/ui/LogiPulseLogo'
import { getDefaultRouteForRole } from '@/config/permissions'
import { ROUTES } from '@/config/routes'
import { getApiErrorMessage } from '@/lib/formatters'
import { analyticsService } from '@/services/analytics.service'
import { useAuth } from '@/stores/auth-context'
import type { UserRole } from '@/types/auth'

const ROLE_OPTIONS: ReadonlyArray<{ value: UserRole; label: string }> = [
  { value: 'ADMIN', label: 'Admin' },
  { value: 'OPERATIONS_MANAGER', label: 'Operations Manager' },
  { value: 'FLEET_MANAGER', label: 'Fleet Manager' },
  { value: 'WAREHOUSE_MANAGER', label: 'Warehouse Manager' },
  { value: 'ANALYST', label: 'Analyst' },
]

export function LoginPage() {
  const { isAuthenticated, user, login, logout, refreshMe } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [selectedRole, setSelectedRole] = useState<UserRole | ''>('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberDevice, setRememberDevice] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const healthQuery = useQuery({
    queryKey: ['system', 'health'],
    queryFn: () => analyticsService.getSystemHealth(),
    retry: false,
  })

  if (!isSubmitting && isAuthenticated && user) {
    const redirectTo =
      (location.state as { from?: string } | null)?.from || getDefaultRouteForRole(user.role)
    return <Navigate to={redirectTo} replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErrorMsg(null)
    setSuccessMsg(null)
    const trimmedId = identifier.trim()
    if (!trimmedId || !password) {
      setErrorMsg('Please enter your username or email and password.')
      return
    }
    if (!selectedRole) {
      setErrorMsg('Please select your role.')
      return
    }

    setIsSubmitting(true)
    try {
      const loginUser = await login(
        { username_or_email: trimmedId, password },
        rememberDevice,
      )
      const verifiedUser = (await refreshMe()) ?? loginUser
      if (!verifiedUser || verifiedUser.role.toUpperCase() !== selectedRole) {
        await logout()
        setErrorMsg('The selected role does not match your account.')
        return
      }

      setSuccessMsg(`Authenticated as ${verifiedUser.full_name} (${verifiedUser.role})`)
      const fromPath = (location.state as { from?: string } | null)?.from
      const destination =
        fromPath && fromPath !== ROUTES.LOGIN
          ? fromPath
          : getDefaultRouteForRole(verifiedUser.role)
      navigate(destination, { replace: true })
    } catch (err) {
      setErrorMsg(getApiErrorMessage(err, 'Invalid username/email or password'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const health = healthQuery.data

  return (
    <div className="flex min-h-screen w-full flex-col lg:flex-row bg-surface-container-lowest">
      {/* LEFT PANEL: BRAND & SYSTEM STATUS (50%) */}
      <div className="relative flex w-full flex-col justify-between overflow-hidden bg-surface-container-lowest p-8 sm:p-12 lg:w-1/2 lg:p-16">
        <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-primary-fixed/5 blur-[120px]" />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              'linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />

        <div className="relative z-10">
          <LogiPulseLogo subtitle="Autonomous Freight OS" />
        </div>

        <div className="relative z-10 my-12 max-w-lg lg:my-auto">
          <h1 className="font-display text-4xl font-bold leading-[1.1] tracking-tight text-primary sm:text-5xl">
            Welcome to <span className="text-primary-fixed">LOGIPULSE</span>
          </h1>
          <p className="mt-5 max-w-md text-base leading-relaxed text-secondary">
            Intelligent logistics. Smarter routes. Reliable deliveries.
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-3 pt-6">
          <span className="relative flex h-2 w-2">
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                health?.status === 'ok' ? 'animate-ping bg-primary-fixed' : 'bg-[#F59E0B]'
              }`}
            />
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                health?.status === 'ok' ? 'bg-primary-fixed' : 'bg-[#F59E0B]'
              }`}
            />
          </span>
          <span className="font-telemetry text-xs text-on-surface-variant">
            {health
              ? `${health.app} v${health.version} • DB ${health.database.connected ? 'Connected' : 'Degraded'}`
              : healthQuery.isError
                ? 'Backend API unreachable at configured base URL'
                : 'Checking backend gateway status...'}
          </span>
        </div>
      </div>

      {/* RIGHT PANEL: AUTHENTICATION FORM (50%) */}
      <div className="flex w-full items-center justify-center bg-surface p-6 sm:p-12 lg:w-1/2 lg:p-16">
        <div className="w-full max-w-md">
          <div className="mb-8">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-display text-3xl font-bold tracking-tight text-primary">
                Sign In
              </h2>
              <span className="rounded bg-surface-container-high px-2.5 py-0.5 font-display text-[10px] font-bold uppercase tracking-wider text-outline">
                JWT AUTH
              </span>
            </div>
            <p className="text-sm text-secondary">
              Authenticate with your LOGIPULSE username or email. Access roles are assigned server-side.
            </p>
          </div>

          {errorMsg && (
            <div className="mb-5 flex items-start gap-2.5 rounded-md border border-[#EF4444]/40 bg-[#93000a]/25 p-3 text-xs text-error">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#F87171]" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="mb-5 flex items-center gap-2 rounded-md border border-primary-fixed/40 bg-primary-fixed/15 p-3 text-xs text-primary-fixed">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label
                htmlFor="identifier"
                className="block font-display text-xs font-semibold uppercase tracking-wider text-secondary"
              >
                Username or Email Address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-outline" />
                <input
                  id="identifier"
                  name="identifier"
                  type="text"
                  autoComplete="username"
                  required
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="ops_manager or ops@logipulse.io"
                  className="w-full rounded border border-surface-container-highest bg-surface-container-low py-3 pl-10 pr-4 text-sm text-primary placeholder:text-outline/60 focus:border-primary-fixed focus:bg-surface-container focus:outline-none"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block font-display text-xs font-semibold uppercase tracking-wider text-secondary"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-outline" />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full rounded border border-surface-container-highest bg-surface-container-low py-3 pl-10 pr-11 text-sm text-primary placeholder:text-outline/60 focus:border-primary-fixed focus:bg-surface-container focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-outline hover:text-primary"
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="role"
                className="block font-display text-xs font-semibold uppercase tracking-wider text-secondary"
              >
                Select Your Role
              </label>
              <div className="relative group">
                <BadgeCheck className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-outline transition-colors group-focus-within:text-primary-fixed" />
                <select
                  id="role"
                  name="role"
                  required
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value as UserRole | '')}
                  className={`w-full appearance-none cursor-pointer rounded border border-surface-container-highest bg-surface-container-low py-3 pl-10 pr-10 text-sm transition-colors focus:border-primary-fixed focus:bg-surface-container focus:outline-none ${
                    selectedRole ? 'text-primary' : 'text-secondary'
                  }`}
                >
                  <option value="" disabled className="bg-surface-container-low text-secondary">
                    Select your role...
                  </option>
                  {ROLE_OPTIONS.map((opt) => (
                    <option
                      key={opt.value}
                      value={opt.value}
                      className="bg-surface-container-low text-primary"
                    >
                      {opt.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-outline transition-colors group-focus-within:text-primary-fixed" />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1 text-xs">
              <label className="flex cursor-pointer items-center gap-2 text-on-surface select-none">
                <input
                  type="checkbox"
                  checked={rememberDevice}
                  onChange={(e) => setRememberDevice(e.target.checked)}
                  className="h-4 w-4 rounded border-outline-variant bg-surface-container-high accent-primary-fixed"
                />
                <span>Keep token on this browser</span>
              </label>
              <span
                className="text-outline"
                title="Self-service password reset is not enabled on the backend API"
              >
                Forgot password? Contact Admin
              </span>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded bg-primary-fixed px-6 py-3.5 font-display text-sm font-bold text-surface-container-lowest shadow-[0_0_20px_rgba(198,244,50,0.2)] transition-all hover:bg-primary-fixed-dim disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>

            <div className="mt-6 flex flex-col items-center space-y-2 pt-4 text-center">
              <div className="inline-flex items-center gap-2 rounded-full bg-surface-container-low px-3 py-1">
                <ShieldCheck className="h-3.5 w-3.5 text-outline" />
                <span className="font-display text-[10px] font-bold uppercase tracking-wider text-outline">
                  Role determined by backend RBAC (/auth/login &amp; /auth/me)
                </span>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}


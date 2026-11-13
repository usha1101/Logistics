import { ShieldAlert } from 'lucide-react'
import { Link, Navigate, useLocation } from 'react-router-dom'

import { LoadingState } from '@/components/ui/PageStates'
import { getDefaultRouteForRole, hasAnyRole } from '@/config/permissions'
import { ROUTES } from '@/config/routes'
import { formatRoleLabel } from '@/lib/formatters'
import { useAuth } from '@/stores/auth-context'
import type { UserRole } from '@/types/auth'

export function ProtectedRoute({
  allowedRoles,
  children,
}: {
  allowedRoles?: readonly UserRole[]
  children: React.ReactNode
}) {
  const { isAuthenticated, isInitializing, user } = useAuth()
  const location = useLocation()

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas p-6">
        <div className="w-full max-w-md">
          <LoadingState message="Verifying JWT session..." />
        </div>
      </div>
    )
  }

  if (!isAuthenticated || !user) {
    return <Navigate to={ROUTES.LOGIN} replace state={{ from: location.pathname }} />
  }

  if (allowedRoles && !hasAnyRole(user.role, allowedRoles)) {
    const fallbackRoute = getDefaultRouteForRole(user.role)
    return (
      <div className="flex min-h-[70vh] items-center justify-center p-6">
        <div className="w-full max-w-md rounded-lg border border-[#EF4444]/40 bg-surface-container-low p-6 text-center shadow-2xl">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#EF4444]/15 text-[#F87171]">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h2 className="font-display text-lg font-bold text-primary">Access Restricted (403)</h2>
          <p className="mt-2 text-xs text-secondary">
            Your backend role (<span className="font-telemetry text-lime">{formatRoleLabel(user.role)}</span>)
            does not have permission to view this screen.
          </p>
          <p className="mt-1 font-telemetry text-[11px] text-outline">
            Permitted roles: {allowedRoles.join(', ')}
          </p>
          <Link
            to={fallbackRoute}
            className="mt-5 inline-flex items-center justify-center rounded bg-primary-fixed px-4 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim transition-colors"
          >
            Return to Permitted Workspace
          </Link>
        </div>
      </div>
    )
  }

  return <>{children}</>
}


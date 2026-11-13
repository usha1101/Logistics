import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

import { AutonomousWelcomeScene } from '@/components/three/AutonomousWelcomeScene'
import { getDefaultRouteForRole } from '@/config/permissions'
import { ROUTES } from '@/config/routes'
import { analyticsService } from '@/services/analytics.service'
import { useAuth } from '@/stores/auth-context'

export function WelcomePage() {
  const { isAuthenticated, user } = useAuth()
  const healthQuery = useQuery({
    queryKey: ['system', 'health'],
    queryFn: () => analyticsService.getSystemHealth(),
    retry: false,
  })

  const health = healthQuery.data
  const targetRoute =
    isAuthenticated && user ? getDefaultRouteForRole(user.role) : ROUTES.LOGIN

  return (
    <main className="relative flex min-h-[100dvh] w-full flex-col justify-between overflow-x-hidden bg-canvas select-none">
      {/* Interactive Three.js 3D Logistics Background + Soft Readability Scrim */}
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <AutonomousWelcomeScene />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(11,11,12,0.56)_0%,_rgba(11,11,12,0.16)_52%,_rgba(11,11,12,0.58)_100%)]" />
        <div className="absolute inset-0 bg-gradient-to-b from-canvas/55 via-transparent to-canvas/80" />
      </div>

      {/* Centered Hero */}
      <div className="relative z-10 mx-auto my-auto flex max-w-4xl flex-col items-center px-6 pt-12 text-center pointer-events-none">
        <div className="pointer-events-auto mb-7 inline-flex items-center gap-2.5 rounded-full border border-white/10 bg-surface-container-high/70 px-4 py-1.5 backdrop-blur-md shadow-[0_0_20px_rgba(198,244,50,0.12)]">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-lime opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-lime" />
          </span>
          <span className="font-display text-[11px] font-semibold uppercase tracking-widest text-lime">
            {health?.status === 'ok'
              ? 'AUTONOMOUS LOGISTICS GRID CONNECTED'
              : healthQuery.isError
                ? 'BACKEND API OFFLINE OR UNREACHABLE'
                : 'AUTONOMOUS LOGISTICS DIGITAL TWIN'}
          </span>
        </div>

        <h1 className="pointer-events-auto font-display text-6xl font-bold leading-[0.92] tracking-[-0.035em] text-primary drop-shadow-[0_10px_28px_rgba(0,0,0,0.85)] sm:text-7xl md:text-8xl lg:text-[104px]">
          LOGI<span className="text-lime drop-shadow-[0_0_32px_rgba(198,244,50,0.45)]">PULSE</span>
        </h1>

        <p className="pointer-events-auto mt-5 max-w-xl text-base text-secondary drop-shadow-[0_4px_16px_rgba(0,0,0,0.9)] sm:text-lg">
          Intelligent logistics. Smarter routes. Reliable deliveries.
        </p>

        <div className="pointer-events-auto mt-9 flex flex-wrap items-center justify-center gap-4">
          <Link
            to={targetRoute}
            className="group inline-flex items-center gap-2.5 rounded-xl bg-lime px-7 py-3.5 font-display text-base font-semibold text-surface-container-lowest transition-all hover:scale-[1.02] hover:shadow-[0_0_32px_rgba(198,244,50,0.5)]"
          >
            <span>{isAuthenticated ? 'Enter Command Workspace' : 'Go to Login'}</span>
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
      </div>

      {/* Bottom Live Health Dock */}
      <footer className="relative z-10 mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-3 border-t border-white/10 px-6 py-4 font-telemetry text-xs text-on-surface-variant backdrop-blur-xs">
        <div className="flex flex-wrap items-center gap-4">
          <span className="inline-flex items-center gap-2 text-on-surface font-semibold">
            <span
              className={`h-2 w-2 rounded-full ${health?.status === 'ok' ? 'bg-lime' : 'bg-[#F59E0B]'
                }`}
            />
            {health
              ? `${health.app} v${health.version} (${health.environment})`
              : 'Waiting for Backend /health'}
          </span>
          <span className="hidden sm:inline text-outline-variant">/</span>
          <span className="hidden sm:inline text-secondary">
            DATABASE:{' '}
            {health
              ? health.database.connected
                ? 'CONNECTED'
                : 'DEGRADED'
              : healthQuery.isLoading
                ? 'CHECKING'
                : 'UNREACHABLE'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-outline" />
          <span className="uppercase tracking-wider text-secondary">
            DATA SOURCE: {health?.data_source ?? 'SIMULATED'}
          </span>
          <CheckCircle2
            className={`h-4 w-4 ${health?.status === 'ok' ? 'text-lime' : 'text-outline'}`}
          />
        </div>
      </footer>
    </main>
  )
}

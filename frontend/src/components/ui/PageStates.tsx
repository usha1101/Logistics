import { AlertTriangle, Info, Loader2, RefreshCw, ShieldAlert, X } from 'lucide-react'
import type { ReactNode } from 'react'

export function LoadingState({ message = 'Synchronizing live backend telemetry...' }: { message?: string }) {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 rounded-lg border border-surface-container-highest bg-surface-container-low p-8 text-center">
      <Loader2 className="h-7 w-7 animate-spin text-lime" />
      <p className="font-telemetry text-xs uppercase tracking-widest text-secondary">{message}</p>
    </div>
  )
}

export function ErrorState({
  title = 'Failed to load backend resource',
  message,
  onRetry,
}: {
  title?: string
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-[#EF4444]/40 bg-[#93000a]/20 p-6 text-center">
      <AlertTriangle className="h-7 w-7 text-[#F87171]" />
      <div>
        <h3 className="font-display text-sm font-semibold text-primary">{title}</h3>
        <p className="mt-1 max-w-lg text-xs text-error">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded bg-surface-container-high px-3 py-1.5 font-display text-xs font-semibold text-primary hover:bg-surface-bright transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry Request
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-surface-container-highest bg-surface-container-lowest/60 p-8 text-center">
      <p className="font-display text-sm font-semibold text-primary">{title}</p>
      <p className="max-w-md text-xs text-secondary">{description}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function UnavailableNotice({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-outline-variant/40 bg-surface-container/60 p-3.5 text-xs">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-outline" />
      <div>
        <div className="font-display font-semibold text-on-surface">{title}</div>
        <div className="mt-0.5 text-secondary">{description}</div>
      </div>
    </div>
  )
}

export function RestrictedBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-[#F59E0B]/40 bg-[#F59E0B]/10 px-4 py-2.5 text-xs text-[#FBBF24]">
      <ShieldAlert className="h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg border border-surface-container-highest bg-surface-container-low p-6 shadow-[0_24px_48px_rgba(0,0,0,0.75)]">
        <div className="mb-4 flex items-center justify-between border-b border-surface-container-highest pb-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-lime" />
            <h3 className="font-display text-base font-bold text-primary">{title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-secondary hover:bg-surface-container hover:text-primary"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}


import type { ReactNode } from 'react'

export function KpiCard({
  label,
  value,
  sublabel,
  icon,
  accent = 'default',
}: {
  label: string
  value: string | number
  sublabel?: string
  icon?: ReactNode
  accent?: 'default' | 'lime' | 'danger' | 'warn' | 'info' | 'success'
}) {
  const valueColor =
    accent === 'lime'
      ? 'text-lime'
      : accent === 'danger'
        ? 'text-[#F87171]'
        : accent === 'warn'
          ? 'text-[#FBBF24]'
          : accent === 'info'
            ? 'text-[#60A5FA]'
            : accent === 'success'
              ? 'text-[#22C55E]'
              : 'text-primary'

  return (
    <div className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-4 flex flex-col justify-between gap-2 transition-colors hover:border-outline-variant/80">
      <div className="flex items-center justify-between gap-2">
        <span className="font-display text-[11px] font-bold uppercase tracking-wider text-outline">
          {label}
        </span>
        {icon && (
          <span className="flex h-7 w-7 items-center justify-center rounded bg-surface-container text-primary-fixed">
            {icon}
          </span>
        )}
      </div>
      <div className={`font-telemetry text-2xl font-bold leading-tight ${valueColor}`}>
        {value}
      </div>
      {sublabel && <div className="text-xs text-secondary truncate">{sublabel}</div>}
    </div>
  )
}


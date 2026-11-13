import { getStatusTone, type BadgeTone } from '@/lib/formatters'

const TONE_CLASSES: Record<BadgeTone, string> = {
  lime: 'bg-primary-fixed/15 text-primary-fixed border-primary-fixed/35',
  success: 'bg-[#22C55E]/15 text-[#22C55E] border-[#22C55E]/35',
  info: 'bg-[#3B82F6]/15 text-[#60A5FA] border-[#3B82F6]/35',
  warn: 'bg-[#F59E0B]/15 text-[#FBBF24] border-[#F59E0B]/35',
  danger: 'bg-[#EF4444]/15 text-[#F87171] border-[#EF4444]/35',
  neutral: 'bg-surface-container-high text-secondary border-outline-variant/40',
}

export function StatusBadge({
  value,
  tone,
  pulse = false,
}: {
  value: string | null | undefined
  tone?: BadgeTone
  pulse?: boolean
}) {
  const resolvedTone = tone ?? getStatusTone(value)
  const label = (value ?? 'UNKNOWN').replace(/_/g, ' ')

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 border font-telemetry text-[11px] font-semibold uppercase tracking-wider whitespace-nowrap ${TONE_CLASSES[resolvedTone]}`}
    >
      {pulse && <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />}
      <span>{label}</span>
    </span>
  )
}


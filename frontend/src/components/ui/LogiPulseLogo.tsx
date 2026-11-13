export function LogiPulseLogo({
  compact = false,
  subtitle,
}: {
  compact?: boolean
  subtitle?: string
}) {
  return (
    <div className="flex items-center gap-3 select-none">
      <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-outline-variant/40 bg-surface-container-high shadow-[0_0_12px_rgba(198,244,50,0.2)]">
        <svg viewBox="0 0 40 40" className="h-7 w-7" fill="none" aria-hidden="true">
          <path
            d="M12 6L28 6L36 20L28 34L12 34L4 20L12 6Z"
            stroke="#C6F432"
            strokeWidth="2.4"
            fill="#14170D"
            fillOpacity="0.85"
          />
          <circle
            cx="20"
            cy="20"
            r="9.5"
            stroke="#C6F432"
            strokeWidth="1"
            strokeDasharray="2 3"
            opacity="0.7"
          />
          <path d="M7 20H15.5M24.5 20H33" stroke="#C6F432" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M20 7V15.5M20 24.5V33" stroke="#C6F432" strokeWidth="1.8" strokeLinecap="round" />
          <circle cx="20" cy="20" r="4" fill="#C6F432" />
        </svg>
      </div>
      {!compact && (
        <div className="flex flex-col leading-none">
          <div className="flex items-center gap-1">
            <span className="font-display text-lg font-bold tracking-wider text-primary">
              LOGI<span className="text-lime">PULSE</span>
            </span>
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-lime" />
          </div>
          {subtitle && (
            <span className="mt-1 font-display text-[10px] font-bold uppercase tracking-[0.18em] text-outline">
              {subtitle}
            </span>
          )}
        </div>
      )}
    </div>
  )
}


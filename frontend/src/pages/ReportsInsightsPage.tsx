import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  BarChart3,
  Clock,
  Download,
  FileText,
  Filter,
  Info,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { KpiCard } from '@/components/ui/KpiCard'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  UnavailableNotice,
} from '@/components/ui/PageStates'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatDateTimeShort, formatNumber, formatPercent, getApiErrorMessage } from '@/lib/formatters'
import { analyticsService, type AnalyticsQueryParams } from '@/services/analytics.service'
import type {
  ReportGenerateRequest,
  ReportMetadataRead,
  ReportType,
  TrendGrouping,
} from '@/types/analytics'

type TimeRangePreset = '24H' | '7D' | '30D' | 'ALL'

const TIME_PRESETS: Array<{ id: TimeRangePreset; label: string }> = [
  { id: '24H', label: 'Last 24h' },
  { id: '7D', label: 'Last 7d' },
  { id: '30D', label: 'Last 30d' },
  { id: 'ALL', label: 'All Time' },
]

const GROUPING_OPTIONS: TrendGrouping[] = ['DAY', 'WEEK', 'MONTH']

const STATUS_BAR_COLORS: Record<string, string> = {
  AVAILABLE: '#22C55E',
  IN_TRANSIT: '#60A5FA',
  IDLE: '#94A3B8',
  MAINTENANCE: '#FBBF24',
  BREAKDOWN: '#F87171',
  OFFLINE: '#52525B',
}

function formatBytes(bytes: number | null): string {
  if (!bytes || bytes <= 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function ReportsInsightsPage() {
  const queryClient = useQueryClient()

  const [timePreset, setTimePreset] = useState<TimeRangePreset>('ALL')
  const [grouping, setGrouping] = useState<TrendGrouping>('DAY')
  const [includeSimulations, setIncludeSimulations] = useState(true)
  const [reportTypeFilter, setReportTypeFilter] = useState<string>('ALL')
  const [generateOpen, setGenerateOpen] = useState(false)
  const [selectedReportType, setSelectedReportType] = useState<ReportType>('EXECUTIVE_SUMMARY')
  const [reportTitle, setReportTitle] = useState('')
  const [includeChartsInPdf, setIncludeChartsInPdf] = useState(true)
  const [actionError, setActionError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const queryParams: AnalyticsQueryParams = useMemo(() => {
    const base: AnalyticsQueryParams = {
      include_simulations: includeSimulations,
    }
    if (timePreset === 'ALL') return base
    const now = new Date()
    const start = new Date(now)
    if (timePreset === '24H') start.setHours(now.getHours() - 24)
    if (timePreset === '7D') start.setDate(now.getDate() - 7)
    if (timePreset === '30D') start.setDate(now.getDate() - 30)
    return {
      ...base,
      start_date: start.toISOString(),
      end_date: now.toISOString(),
    }
  }, [includeSimulations, timePreset])

  const overviewQuery = useQuery({
    queryKey: ['analytics', 'overview', queryParams],
    queryFn: () => analyticsService.getOverview(queryParams),
  })

  const ordersQuery = useQuery({
    queryKey: ['analytics', 'orders', queryParams],
    queryFn: () => analyticsService.getOrders(queryParams),
  })

  const orderTrendsQuery = useQuery({
    queryKey: ['analytics', 'order-trends', queryParams, grouping],
    queryFn: () => analyticsService.getOrderTrends({ ...queryParams, grouping }),
  })

  const fleetQuery = useQuery({
    queryKey: ['analytics', 'fleet', queryParams],
    queryFn: () => analyticsService.getFleet(queryParams),
  })

  const disruptionsQuery = useQuery({
    queryKey: ['analytics', 'disruptions', queryParams],
    queryFn: () => analyticsService.getDisruptions(queryParams),
  })

  const disruptionTrendsQuery = useQuery({
    queryKey: ['analytics', 'disruption-trends', queryParams, grouping],
    queryFn: () => analyticsService.getDisruptionTrends({ ...queryParams, grouping }),
  })

  const recoveryQuery = useQuery({
    queryKey: ['analytics', 'recovery', queryParams],
    queryFn: () => analyticsService.getRecovery(queryParams),
  })

  const agentsQuery = useQuery({
    queryKey: ['analytics', 'agents', queryParams],
    queryFn: () => analyticsService.getAgents(queryParams),
  })

  const comparisonsQuery = useQuery({
    queryKey: ['analytics', 'comparisons', queryParams],
    queryFn: () => analyticsService.getComparisons(queryParams),
  })

  const reportTypesQuery = useQuery({
    queryKey: ['reports', 'types'],
    queryFn: () => analyticsService.getReportTypes(),
  })

  const reportsQuery = useQuery({
    queryKey: ['reports', 'list', reportTypeFilter],
    queryFn: () =>
      analyticsService.listReports({
        skip: 0,
        limit: 25,
        ...(reportTypeFilter !== 'ALL' ? { report_type: reportTypeFilter } : {}),
      }),
  })

  const generateMutation = useMutation({
    mutationFn: (payload: ReportGenerateRequest) => analyticsService.generateReport(payload),
    onSuccess: () => {
      setActionError(null)
      setGenerateOpen(false)
      setReportTitle('')
      void queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (err) => {
      setActionError(getApiErrorMessage(err, 'Failed to generate PDF report'))
    },
  })

  const handleGenerateReport = (e: React.FormEvent) => {
    e.preventDefault()
    setActionError(null)
    generateMutation.mutate({
      report_type: selectedReportType,
      title: reportTitle.trim() || undefined,
      start_date: queryParams.start_date,
      end_date: queryParams.end_date,
      include_simulations: includeSimulations,
      include_charts: includeChartsInPdf,
    })
  }

  const handleDownloadPdf = async (report: ReportMetadataRead) => {
    setActionError(null)
    setDownloadingId(report.id)
    try {
      const safeName =
        report.file_name || `${report.report_code || report.report_type}.pdf`
      await analyticsService.downloadReport(report.id, safeName)
    } catch (err) {
      setActionError(getApiErrorMessage(err, 'Failed to download report PDF'))
    } finally {
      setDownloadingId(null)
    }
  }

  const fleetStatusChartData = useMemo(() => {
    if (!fleetQuery.data) return []
    return Object.entries(fleetQuery.data.vehicles_by_status).map(([status, count]) => ({
      status: status.replace(/_/g, ' '),
      rawStatus: status,
      count,
    }))
  }, [fleetQuery.data])

  const orderStatusChartData = useMemo(() => {
    if (!ordersQuery.data) return []
    return Object.entries(ordersQuery.data.orders_by_status).map(([status, count]) => ({
      status: status.replace(/_/g, ' '),
      count,
    }))
  }, [ordersQuery.data])

  const combinedUnavailableMetrics = useMemo(() => {
    const items = new Set<string>()
    overviewQuery.data?.unavailable_metrics.forEach((m) => items.add(m))
    ordersQuery.data?.unavailable_metrics.forEach((m) => items.add(m))
    fleetQuery.data?.unavailable_metrics.forEach((m) => items.add(m))
    disruptionsQuery.data?.unavailable_metrics.forEach((m) => items.add(m))
    agentsQuery.data?.unavailable_metrics.forEach((m) => items.add(m))
    recoveryQuery.data?.unavailable_metrics.forEach((m) => items.add(m))
    return Array.from(items)
  }, [
    agentsQuery.data,
    disruptionsQuery.data,
    fleetQuery.data,
    ordersQuery.data,
    overviewQuery.data,
    recoveryQuery.data,
  ])

  const overview = overviewQuery.data
  const orders = ordersQuery.data
  const fleet = fleetQuery.data
  const disruptions = disruptionsQuery.data
  const recovery = recoveryQuery.data
  const agents = agentsQuery.data
  const comparisons = comparisonsQuery.data
  const reports = reportsQuery.data?.items ?? []
  const reportTypes = reportTypesQuery.data?.report_types ?? []

  if (overviewQuery.isLoading && !overview) {
    return <LoadingState message="Aggregating operational analytics & reports..." />
  }

  if (overviewQuery.isError) {
    return (
      <ErrorState
        title="Unable to load Analytics Overview"
        message={getApiErrorMessage(overviewQuery.error)}
        onRetry={() => void overviewQuery.refetch()}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Top Filter Bar & PDF Export CTA */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 rounded-md bg-surface-container p-1 border border-outline-variant/40">
            {TIME_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => setTimePreset(preset.id)}
                className={`rounded px-3 py-1.5 font-display text-xs font-semibold transition-colors ${timePreset === preset.id
                    ? 'bg-primary-fixed text-on-primary-fixed'
                    : 'text-secondary hover:text-primary'
                  }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 rounded-md bg-surface-container p-1 border border-outline-variant/40">
            <span className="px-2 font-telemetry text-[10px] uppercase tracking-wider text-outline">
              Group:
            </span>
            {GROUPING_OPTIONS.map((grp) => (
              <button
                key={grp}
                type="button"
                onClick={() => setGrouping(grp)}
                className={`rounded px-2.5 py-1 font-telemetry text-[11px] font-semibold transition-colors ${grouping === grp
                    ? 'bg-surface-bright text-lime border border-lime/30'
                    : 'text-secondary hover:text-primary'
                  }`}
              >
                {grp}
              </button>
            ))}
          </div>

          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-outline-variant/40 bg-surface-container px-3 py-1.5 text-xs text-secondary hover:text-primary">
            <input
              type="checkbox"
              checked={includeSimulations}
              onChange={(e) => setIncludeSimulations(e.target.checked)}
              className="accent-[#c5f331]"
            />
            <span>Include Simulated Data</span>
          </label>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: ['analytics'] })
              void queryClient.invalidateQueries({ queryKey: ['reports'] })
            }}
            className="inline-flex items-center gap-1.5 rounded border border-outline-variant bg-surface-container px-3 py-2 font-display text-xs font-semibold text-primary hover:bg-surface-container-high transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setGenerateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-4 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim transition-colors"
          >
            <Plus className="h-4 w-4" />
            Generate PDF Report
          </button>
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg border border-[#EF4444]/40 bg-[#93000a]/20 px-4 py-3 text-xs text-error">
          {actionError}
        </div>
      )}

      {/* 4 Top KPI Summary Cards */}
      {overview && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Delivery Success Rate"
            value={formatPercent(overview.delivery_success_rate)}
            sublabel={`${formatNumber(overview.delivered_orders)} / ${formatNumber(overview.total_orders)} delivered • OTDR ${formatPercent(overview.on_time_delivery_rate)}`}
            icon={<TrendingUp className="h-4 w-4" />}
            accent="lime"
          />
          <KpiCard
            label="Fleet Utilization"
            value={formatPercent(overview.fleet_utilization_rate)}
            sublabel={`${formatNumber(overview.active_vehicles)} active of ${formatNumber(overview.total_vehicles)} vehicles • Cap ${formatPercent(fleet?.fleet_capacity_utilization_percentage)}`}
            icon={<Activity className="h-4 w-4" />}
            accent="info"
          />
          <KpiCard
            label="Recovery Success Rate"
            value={formatPercent(overview.recovery_success_rate)}
            sublabel={`${formatNumber(overview.executed_recovery_plans)} / ${formatNumber(overview.total_recovery_plans)} plans executed • Delay saved ${formatNumber(recovery?.estimated_delay_reduction_minutes)}m`}
            icon={<ShieldCheck className="h-4 w-4" />}
            accent="success"
          />
          <KpiCard
            label="Disruption & AI Runs"
            value={`${formatNumber(overview.active_disruptions)} Active`}
            sublabel={`${formatNumber(overview.resolved_disruptions)} resolved • ${formatNumber(overview.total_agent_runs)} AI runs (${formatPercent(agents?.agent_success_rate)} ok)`}
            icon={<Clock className="h-4 w-4" />}
            accent={overview.active_disruptions > 0 ? 'warn' : 'default'}
          />
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Order Delivery Trends */}
        <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-sm font-bold text-primary">
                Order Volume & Delivery Trends
              </h2>
              <p className="text-xs text-secondary">
                {orderTrendsQuery.data?.notes ||
                  `Grouped by ${grouping.toLowerCase()} (${orderTrendsQuery.data?.unit ?? 'count'})`}
              </p>
            </div>
            <StatusBadge
              value={orderTrendsQuery.data?.is_historical ? 'HISTORICAL' : 'SNAPSHOT'}
              tone="neutral"
            />
          </div>
          <div className="h-64 w-full">
            {orderTrendsQuery.isLoading ? (
              <LoadingState message="Loading order trends..." />
            ) : (orderTrendsQuery.data?.data_points.length ?? 0) === 0 ? (
              <EmptyState
                title="No Order Trend Points"
                description="No order records match the selected date range and simulation filter."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={orderTrendsQuery.data?.data_points ?? []}>
                  <defs>
                    <linearGradient id="limeAreaGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#c5f331" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#c5f331" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#292a2c" />
                  <XAxis dataKey="period" stroke="#909284" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#909284" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#131314',
                      borderColor: '#45483c',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  <Area
                    type="monotone"
                    dataKey="value"
                    name="Orders"
                    stroke="#c5f331"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#limeAreaGrad)"
                  />
                  <Area
                    type="monotone"
                    dataKey="breakdown.orders_delivered"
                    name="Delivered"
                    stroke="#22C55E"
                    strokeWidth={2}
                    fillOpacity={0}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Disruption Trends */}
        <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-sm font-bold text-primary">
                Disruption Incident Timeline
              </h2>
              <p className="text-xs text-secondary">
                {disruptionTrendsQuery.data?.notes ||
                  `Grouped by ${grouping.toLowerCase()} • Est. delay ${formatNumber(disruptions?.estimated_total_delay_minutes)} mins`}
              </p>
            </div>
            <StatusBadge
              value={
                disruptions
                  ? `${disruptions.total_disruptions} INCIDENTS`
                  : 'LOADING'
              }
              tone="warn"
            />
          </div>
          <div className="h-64 w-full">
            {disruptionTrendsQuery.isLoading ? (
              <LoadingState message="Loading disruption trends..." />
            ) : (disruptionTrendsQuery.data?.data_points.length ?? 0) === 0 ? (
              <EmptyState
                title="No Disruption Trend Points"
                description="No disruptions recorded for the selected time window."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={disruptionTrendsQuery.data?.data_points ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#292a2c" />
                  <XAxis dataKey="period" stroke="#909284" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#909284" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#131314',
                      borderColor: '#45483c',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  <Bar
                    dataKey="value"
                    name="Disruptions"
                    fill="#F59E0B"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="secondary_value"
                    name="Resolved"
                    fill="#22C55E"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Fleet Status Breakdown */}
        <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-sm font-bold text-primary">
                Fleet Status & Load Utilization
              </h2>
              <p className="text-xs text-secondary">
                {fleet
                  ? `${formatNumber(fleet.total_current_load_kg)} / ${formatNumber(fleet.total_fleet_capacity_kg)} kg total payload (${formatPercent(fleet.average_load_utilization_percentage)} avg)`
                  : 'Loading fleet breakdown...'}
              </p>
            </div>
            <BarChart3 className="h-4 w-4 text-outline" />
          </div>
          <div className="h-56 w-full">
            {fleetStatusChartData.length === 0 ? (
              <EmptyState
                title="No Fleet Metrics"
                description="No vehicle analytics records available."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={fleetStatusChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#292a2c" />
                  <XAxis dataKey="status" stroke="#909284" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#909284" tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#131314',
                      borderColor: '#45483c',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" name="Vehicles" radius={[4, 4, 0, 0]}>
                    {fleetStatusChartData.map((entry) => (
                      <Cell
                        key={entry.rawStatus}
                        fill={STATUS_BAR_COLORS[entry.rawStatus] ?? '#c5f331'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* Order Status Breakdown */}
        <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5">
          <div className="mb-4 flex items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-sm font-bold text-primary">
                Order Lifecycle Distribution
              </h2>
              <p className="text-xs text-secondary">
                {orders
                  ? `Eligible: ${formatNumber(orders.eligible_orders)} • On-Time: ${formatNumber(orders.on_time_delivered_orders)} • Late: ${formatNumber(orders.late_delivered_orders)}`
                  : 'Loading order analytics...'}
              </p>
            </div>
            <StatusBadge
              value={orders ? `${formatNumber(orders.total_order_weight_kg)} KG` : 'ORDERS'}
              tone="info"
            />
          </div>
          <div className="h-56 w-full">
            {orderStatusChartData.length === 0 ? (
              <EmptyState
                title="No Order Metrics"
                description="No order status breakdown returned for the active filter."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={orderStatusChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#292a2c" />
                  <XAxis dataKey="status" stroke="#909284" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#909284" tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#131314',
                      borderColor: '#45483c',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="count" name="Orders" fill="#60A5FA" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </div>

      {/* Before vs After Recovery Performance Comparisons */}
      <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-display text-sm font-bold text-primary">
              Before vs After Recovery Performance Comparisons
            </h2>
            <p className="text-xs text-secondary">
              Scope: {comparisons?.comparison_scope ?? 'GLOBAL'} • Evaluated:{' '}
              {comparisons?.total_comparisons_evaluated ?? 0} metrics
            </p>
          </div>
          {recovery && (
            <div className="flex flex-wrap items-center gap-3 font-telemetry text-xs">
              <span className="text-secondary">
                Reassigned Proposed:{' '}
                <strong className="text-primary">
                  {formatNumber(recovery.total_reassigned_orders_proposed)}
                </strong>
              </span>
              <span className="text-secondary">
                Recovered Orders:{' '}
                <strong className="text-[#22C55E]">
                  {formatNumber(recovery.total_recovered_orders)}
                </strong>
              </span>
              <span className="text-secondary">
                Est. Cost Delta:{' '}
                <strong className="text-lime">{formatNumber(recovery.estimated_cost_change, 2)}</strong>
              </span>
            </div>
          )}
        </div>

        {(comparisons?.metrics.length ?? 0) === 0 ? (
          <EmptyState
            title="No Comparison Evaluations Available"
            description="No completed recovery plan comparison pairs exist for the selected scope."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-surface-container-highest bg-surface-container/60 font-telemetry text-[11px] uppercase tracking-wider text-outline">
                <tr>
                  <th className="px-4 py-2.5">Metric</th>
                  <th className="px-4 py-2.5">Before</th>
                  <th className="px-4 py-2.5">After</th>
                  <th className="px-4 py-2.5">Delta</th>
                  <th className="px-4 py-2.5">% Change</th>
                  <th className="px-4 py-2.5">Classification</th>
                  <th className="px-4 py-2.5">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-highest/50">
                {comparisons?.metrics.map((metric) => (
                  <tr key={metric.metric_name} className="hover:bg-surface-container/40">
                    <td className="px-4 py-2.5 font-semibold text-primary">
                      {metric.label}
                      <span className="ml-1.5 font-telemetry text-[10px] text-outline">
                        ({metric.unit})
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-telemetry text-secondary">
                      {metric.before_value !== null ? formatNumber(metric.before_value, 2) : 'N/A'}
                    </td>
                    <td className="px-4 py-2.5 font-telemetry text-primary">
                      {metric.after_value !== null ? formatNumber(metric.after_value, 2) : 'N/A'}
                    </td>
                    <td className="px-4 py-2.5 font-telemetry text-secondary">
                      {metric.absolute_difference !== null
                        ? formatNumber(metric.absolute_difference, 2)
                        : 'N/A'}
                    </td>
                    <td className="px-4 py-2.5 font-telemetry">
                      {metric.percentage_change !== null
                        ? `${metric.percentage_change > 0 ? '+' : ''}${metric.percentage_change.toFixed(1)}%`
                        : 'N/A'}
                    </td>
                    <td className="px-4 py-2.5 font-telemetry text-[11px] text-outline">
                      {metric.data_classification}
                    </td>
                    <td className="px-4 py-2.5">
                      {metric.is_improved === null ? (
                        <StatusBadge value="NEUTRAL" tone="neutral" />
                      ) : metric.is_improved ? (
                        <StatusBadge value="IMPROVED" tone="success" />
                      ) : (
                        <StatusBadge value="DEGRADED" tone="danger" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* PDF Report Archive & Download Center */}
      <section className="rounded-lg border border-surface-container-highest/70 bg-surface-container-low p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <FileText className="h-5 w-5 text-lime" />
            <div>
              <h2 className="font-display text-sm font-bold text-primary">
                PDF Report Export Archive
              </h2>
              <p className="text-xs text-secondary">
                Generated server-side via ReportLab (`/reports/generate` & `/reports/:id/download`)
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-outline" />
            <select
              value={reportTypeFilter}
              onChange={(e) => setReportTypeFilter(e.target.value)}
              className="rounded border border-outline-variant bg-surface-container px-2.5 py-1.5 font-telemetry text-xs text-primary focus:border-lime focus:outline-none"
            >
              <option value="ALL">All Report Types</option>
              {reportTypes.map((rt) => (
                <option key={rt.report_type} value={rt.report_type}>
                  {rt.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {reportsQuery.isLoading ? (
          <LoadingState message="Loading report archive..." />
        ) : reportsQuery.isError ? (
          <ErrorState
            message={getApiErrorMessage(reportsQuery.error)}
            onRetry={() => void reportsQuery.refetch()}
          />
        ) : reports.length === 0 ? (
          <EmptyState
            title="No Generated Reports Yet"
            description="Create an Executive Summary, Fleet, Warehouse, Disruption, AI Intelligence, Recovery, or Simulation PDF report."
            action={
              <button
                type="button"
                onClick={() => setGenerateOpen(true)}
                className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-3.5 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim"
              >
                <Plus className="h-3.5 w-3.5" />
                Generate First Report
              </button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-surface-container-highest bg-surface-container/60 font-telemetry text-[11px] uppercase tracking-wider text-outline">
                <tr>
                  <th className="px-4 py-2.5">Code / Title</th>
                  <th className="px-4 py-2.5">Report Type</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Simulations</th>
                  <th className="px-4 py-2.5">File Size</th>
                  <th className="px-4 py-2.5">Generated</th>
                  <th className="px-4 py-2.5 text-right">PDF Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-highest/50">
                {reports.map((report) => (
                  <tr key={report.id} className="hover:bg-surface-container/40">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-primary">{report.title}</div>
                      <div className="font-telemetry text-[11px] text-outline">
                        {report.report_code}
                      </div>
                      {report.error_message && (
                        <div className="mt-1 text-[11px] text-[#F87171]">
                          {report.error_message}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 font-telemetry text-[11px] text-secondary">
                      {report.report_type.replace(/_/g, ' ')}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={report.status} />
                    </td>
                    <td className="px-4 py-3 font-telemetry text-secondary">
                      {report.include_simulations ? 'INCLUDED' : 'EXCLUDED'}
                    </td>
                    <td className="px-4 py-3 font-telemetry text-secondary">
                      {formatBytes(report.file_size)}
                    </td>
                    <td className="px-4 py-3 font-telemetry text-secondary">
                      {formatDateTimeShort(report.generated_at ?? report.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {report.status === 'COMPLETED' ? (
                        <button
                          type="button"
                          onClick={() => void handleDownloadPdf(report)}
                          disabled={downloadingId === report.id}
                          className="inline-flex items-center gap-1.5 rounded border border-lime/40 bg-primary-fixed/10 px-3 py-1.5 font-display text-xs font-semibold text-lime hover:bg-primary-fixed/20 disabled:opacity-50"
                        >
                          {downloadingId === report.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Download className="h-3.5 w-3.5" />
                          )}
                          Download PDF
                        </button>
                      ) : (
                        <span className="font-telemetry text-[11px] text-outline">
                          Not Ready
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Backend-Reported Unavailable Metrics Disclosure */}
      {combinedUnavailableMetrics.length > 0 && (
        <UnavailableNotice
          title="Backend-Disclosed Unavailable Metrics"
          description={`The backend currently flags these metrics as unavailable without external GPS/billing telemetry: ${combinedUnavailableMetrics.join(', ')}. Real-time distance metrics become available when simulation telemetry records distance_travelled_km.`}
        />
      )}

      {/* Generate Report Modal */}
      <Modal
        open={generateOpen}
        onClose={() => setGenerateOpen(false)}
        title="Generate PDF Analytics Report"
      >
        <form onSubmit={handleGenerateReport} className="space-y-4 text-xs">
          <div>
            <label className="mb-1.5 block font-telemetry text-[11px] uppercase tracking-wider text-outline">
              Report Template
            </label>
            <select
              value={selectedReportType}
              onChange={(e) => setSelectedReportType(e.target.value as ReportType)}
              className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 text-xs text-primary focus:border-lime focus:outline-none"
            >
              {(reportTypes.length > 0
                ? reportTypes
                : [
                  {
                    report_type: 'EXECUTIVE_SUMMARY',
                    title: 'Executive Summary',
                    description: 'Cross-domain operational report',
                    included_sections: [],
                  },
                ]
              ).map((rt) => (
                <option key={rt.report_type} value={rt.report_type}>
                  {rt.title} ({rt.report_type})
                </option>
              ))}
            </select>
            {reportTypes.find((r) => r.report_type === selectedReportType) && (
              <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-secondary">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-outline" />
                <span>
                  {
                    reportTypes.find((r) => r.report_type === selectedReportType)
                      ?.description
                  }
                </span>
              </p>
            )}
          </div>

          <div>
            <label className="mb-1.5 block font-telemetry text-[11px] uppercase tracking-wider text-outline">
              Custom Report Title (Optional)
            </label>
            <input
              type="text"
              value={reportTitle}
              onChange={(e) => setReportTitle(e.target.value)}
              placeholder="e.g. Bengaluru Corridor Daily Review"
              maxLength={200}
              className="w-full rounded border border-outline-variant bg-surface-container px-3 py-2 text-xs text-primary placeholder:text-outline focus:border-lime focus:outline-none"
            />
          </div>

          <div className="flex flex-col gap-2 rounded border border-surface-container-highest bg-surface-container p-3">
            <label className="inline-flex cursor-pointer items-center gap-2 text-secondary">
              <input
                type="checkbox"
                checked={includeChartsInPdf}
                onChange={(e) => setIncludeChartsInPdf(e.target.checked)}
                className="accent-[#c5f331]"
              />
              <span>Include embedded charts & trend tables (`include_charts`)</span>
            </label>
            <div className="font-telemetry text-[11px] text-outline">
              Active Filter Scope: {timePreset} • Simulations:{' '}
              {includeSimulations ? 'Included' : 'Excluded'}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setGenerateOpen(false)}
              className="rounded border border-outline-variant px-4 py-2 font-display text-xs font-semibold text-secondary hover:text-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={generateMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded bg-primary-fixed px-4 py-2 font-display text-xs font-bold text-on-primary-fixed hover:bg-primary-fixed-dim disabled:opacity-60"
            >
              {generateMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Generate Report
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}


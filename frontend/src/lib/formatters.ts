import axios from 'axios'

import type { BackendErrorEnvelope } from '@/types/common'

export type BadgeTone = 'lime' | 'success' | 'info' | 'warn' | 'danger' | 'neutral'

export function getStatusTone(value: string | null | undefined): BadgeTone {
  const normalized = (value ?? '').trim().toUpperCase()
  if (!normalized) {
    return 'neutral'
  }

  if (
    [
      'ACTIVE',
      'RUNNING',
      'ONLINE',
      'OPTIMAL',
      'PRIMARY',
      'LIVE',
    ].includes(normalized)
  ) {
    return 'lime'
  }

  if (
    [
      'AVAILABLE',
      'DELIVERED',
      'COMPLETED',
      'RESOLVED',
      'APPROVED',
      'EXECUTED',
      'FEASIBLE',
      'READY',
      'HEALTHY',
      'OK',
      'SUCCESS',
      'LOW',
    ].includes(normalized)
  ) {
    return 'success'
  }

  if (
    [
      'IN_TRANSIT',
      'ASSIGNED',
      'PICKED',
      'CONFIRMED',
      'GENERATING',
      'SIMULATED',
      'ESTIMATED',
      'ACTUAL',
      'NORMAL',
      'MEDIUM',
      'STANDARD',
    ].includes(normalized)
  ) {
    return 'info'
  }

  if (
    [
      'PENDING',
      'PAUSED',
      'MAINTENANCE',
      'DELAYED',
      'PARTIALLY_FEASIBLE',
      'WARNING',
      'DEGRADED',
      'HIGH',
      'IDLE',
      'CONGESTED',
    ].includes(normalized)
  ) {
    return 'warn'
  }

  if (
    [
      'BREAKDOWN',
      'CANCELLED',
      'FAILED',
      'CRITICAL',
      'REJECTED',
      'INFEASIBLE',
      'BLOCKED',
      'SEVERE',
      'URGENT',
      'OUT_OF_STOCK',
    ].includes(normalized)
  ) {
    return 'danger'
  }

  return 'neutral'
}

export function formatNumber(
  value: number | null | undefined,
  maximumFractionDigits = 0,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return new Intl.NumberFormat('en-IN', {
    maximumFractionDigits,
  }).format(value)
}

export function formatPercent(
  value: number | null | undefined,
  decimals = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }
  return `${value.toFixed(decimals)}%`
}

export function formatDateTimeShort(iso: string | null | undefined): string {
  if (!iso) {
    return '—'
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatRoleLabel(role: string | null | undefined): string {
  if (!role) {
    return '—'
  }
  return role
    .toLowerCase()
    .split('_')
    .map((word) => (word.length > 0 ? word[0].toUpperCase() + word.slice(1) : word))
    .join(' ')
}

export function getApiErrorMessage(
  error: unknown,
  fallback = 'An unexpected error occurred. Please try again.',
): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | Partial<BackendErrorEnvelope>
      | { detail?: unknown; message?: string }
      | string
      | undefined

    if (typeof data === 'string' && data.trim().length > 0) {
      return data
    }

    if (data && typeof data === 'object') {
      if ('error' in data && data.error && typeof data.error.message === 'string') {
        return data.error.message
      }

      if ('detail' in data && data.detail !== undefined) {
        if (typeof data.detail === 'string') {
          return data.detail
        }
        if (Array.isArray(data.detail) && data.detail.length > 0) {
          const first = data.detail[0] as { msg?: string }
          if (first && typeof first.msg === 'string') {
            return first.msg
          }
        }
      }

      if ('message' in data && typeof data.message === 'string') {
        return data.message
      }
    }

    if (typeof error.message === 'string' && error.message.trim().length > 0) {
      return error.message
    }
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message
  }

  return fallback
}

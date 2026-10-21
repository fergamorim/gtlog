import type { Level } from '../api/types'

/** HTTP status classes offered by the filter; `1xx` only appears when the data has such codes. */
export const STATUS_CLASSES = ['1xx', '2xx', '3xx', '4xx', '5xx'] as const

const CODE_RE = /^[1-5]\d\d$/
const CLASS_RE = /^[1-5]xx$/

/** Normalizes a `status` filter value (exact code 100-599 or class `1xx`..`5xx`); null when invalid. */
export function normalizeStatus(value: string): string | null {
  const v = value.trim().toLowerCase()
  return CODE_RE.test(v) || CLASS_RE.test(v) ? v : null
}

const CRITICAL_CODES = new Set([502, 503, 504])

/**
 * Level correlated to an HTTP status code or class, mirroring "Códigos HTTP e níveis" in docs/api.md:
 * 1xx DEBUG, 2xx/3xx INFO, 4xx WARNING, 502/503/504 CRITICAL, other 5xx ERROR.
 * The `5xx` class maps to ERROR (its most common level). Returns null for anything else.
 */
export function levelForStatus(status: number | string | null | undefined): Level | null {
  if (status == null) return null
  const value = normalizeStatus(String(status))
  if (!value) return null
  if (CODE_RE.test(value) && CRITICAL_CODES.has(Number(value))) return 'CRITICAL'
  switch (value[0]) {
    case '1':
      return 'DEBUG'
    case '2':
    case '3':
      return 'INFO'
    case '4':
      return 'WARNING'
    default:
      return 'ERROR'
  }
}

/** Levels shown next to a filter option: the `5xx` class spans ERROR and CRITICAL (502/503/504). */
export function statusLevels(status: string): Level[] {
  if (normalizeStatus(status) === '5xx') return ['ERROR', 'CRITICAL']
  const level = levelForStatus(status)
  return level ? [level] : []
}

/** Filter options: classes (2xx..5xx, plus 1xx when present) followed by the distinct codes from the facets. */
export function statusOptions(codes: number[]): string[] {
  const classes = STATUS_CLASSES.filter((c) => c !== '1xx' || codes.some((code) => code < 200))
  return [...classes, ...[...new Set(codes)].sort((a, b) => a - b).map(String)]
}

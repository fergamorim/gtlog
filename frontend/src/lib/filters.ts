import { LEVELS, type Level } from '../api/types'

/** Filters shared by the logs page and the dashboard. URL params use the same names as the API. */
export interface LogFilters {
  level: Level[]
  service: string[]
  category: string[]
  importId: number | null
  /** ISO 8601 (UTC), inclusive. */
  start: string | null
  /** ISO 8601 (UTC), exclusive. */
  end: string | null
  q: string
}

export type FilterKey = keyof LogFilters

export const EMPTY_FILTERS: LogFilters = {
  level: [],
  service: [],
  category: [],
  importId: null,
  start: null,
  end: null,
  q: '',
}

/** URL/API parameter names owned by the filter model; other params (e.g. `log`) are preserved. */
export const FILTER_PARAMS = ['level', 'service', 'category', 'import_id', 'start', 'end', 'q'] as const

/** Filters the dashboard applies (level and text search are specific to the logs page). */
export const DASHBOARD_FILTER_KEYS: FilterKey[] = ['service', 'category', 'importId', 'start', 'end']

function unique(values: string[]): string[] {
  return [...new Set(values.map((v) => v.trim()).filter(Boolean))]
}

function parseDate(value: string | null): string | null {
  if (!value) return null
  return Number.isNaN(Date.parse(value)) ? null : value
}

export function parseFilters(params: URLSearchParams): LogFilters {
  const importId = Number(params.get('import_id'))
  return {
    level: LEVELS.filter((level) => params.getAll('level').some((v) => v.toUpperCase() === level)),
    service: unique(params.getAll('service')),
    category: unique(params.getAll('category')),
    importId: Number.isInteger(importId) && importId > 0 ? importId : null,
    start: parseDate(params.get('start')),
    end: parseDate(params.get('end')),
    q: params.get('q')?.trim() ?? '',
  }
}

/** Serializes filters into API/URL params, in a stable order (so it is also a good query key). */
export function toParams(filters: LogFilters, keys?: FilterKey[]): URLSearchParams {
  const include = (key: FilterKey) => !keys || keys.includes(key)
  const params = new URLSearchParams()
  if (include('level')) filters.level.forEach((v) => params.append('level', v))
  if (include('service')) filters.service.forEach((v) => params.append('service', v))
  if (include('category')) filters.category.forEach((v) => params.append('category', v))
  if (include('importId') && filters.importId != null) params.set('import_id', String(filters.importId))
  if (include('start') && filters.start) params.set('start', filters.start)
  if (include('end') && filters.end) params.set('end', filters.end)
  if (include('q') && filters.q.trim()) params.set('q', filters.q.trim())
  return params
}

/** Replaces the filter params of `base`, keeping unrelated params intact. */
export function writeFilters(base: URLSearchParams, filters: LogFilters): URLSearchParams {
  const next = new URLSearchParams(base)
  FILTER_PARAMS.forEach((key) => next.delete(key))
  toParams(filters).forEach((value, key) => next.append(key, value))
  return next
}

export function countActiveFilters(filters: LogFilters, keys?: FilterKey[]): number {
  const include = (key: FilterKey) => !keys || keys.includes(key)
  let count = 0
  if (include('level') && filters.level.length) count++
  if (include('service') && filters.service.length) count++
  if (include('category') && filters.category.length) count++
  if (include('importId') && filters.importId != null) count++
  if ((include('start') && filters.start) || (include('end') && filters.end)) count++
  if (include('q') && filters.q) count++
  return count
}

/** Copies only `keys` from `filters`; everything else is reset. */
export function pickFilters(filters: LogFilters, keys: FilterKey[]): LogFilters {
  const picked: LogFilters = { ...EMPTY_FILTERS }
  for (const key of keys) (picked as unknown as Record<FilterKey, unknown>)[key] = filters[key]
  return picked
}

/** Builds a `?query` string for links, e.g. from the dashboard into the logs page. */
export function filtersSearch(filters: LogFilters): string {
  const query = toParams(filters).toString()
  return query ? `?${query}` : ''
}

/**
 * Turns a grouped error message into a phrase query for the backend (quoted = websearch phrase match).
 * Tokens with the `#` placeholder never match literally, so they split the message into separate
 * quoted phrases, ANDed by the backend: "payment # declined" -> `"payment" "declined"`,
 * "timeout calling auth after #ms" -> `"timeout calling auth after"`. Existing quotes are stripped.
 */
export function messageToQuery(message: string): string {
  const phrases: string[][] = [[]]
  for (const token of message.replace(/"/g, ' ').split(/\s+/)) {
    if (!token) continue
    if (token.includes('#')) phrases.push([])
    else phrases[phrases.length - 1].push(token)
  }
  return phrases
    .filter((words) => words.length)
    .map((words) => `"${words.join(' ')}"`)
    .join(' ')
}

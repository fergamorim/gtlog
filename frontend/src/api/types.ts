// Types mirroring the contract in docs/api.md.

export const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const
export type Level = (typeof LEVELS)[number]
export type LevelCounts = Record<Level, number>

export type ImportStatus = 'PENDING' | 'PROCESSING' | 'DONE' | 'FAILED'

export interface ImportJob {
  id: number
  filename: string
  status: ImportStatus
  format: string | null
  total_lines: number | null
  parsed_lines: number
  invalid_lines: number
  error: string | null
  created_at: string
  finished_at: string | null
}

export interface LogEntry {
  id: number
  import_id: number
  timestamp: string
  level: Level
  service: string | null
  category: string | null
  message: string
  raw: string
}

export interface LogPage {
  items: LogEntry[]
  next_cursor: string | null
}

export interface Facets {
  services: string[]
  categories: string[]
}

export type Bucket = 'hour' | 'day'

export type TimeseriesPoint = LevelCounts & { bucket: string }

export interface ServiceStat {
  service: string
  total: number
  errors: number
}

export interface CategoryStat {
  category: string
  total: number
}

export interface TopError {
  message: string
  count: number
  last_seen: string
}

export interface Stats {
  total: number
  by_level: LevelCounts
  error_rate: number
  first_timestamp: string | null
  last_timestamp: string | null
  bucket: Bucket
  timeseries: TimeseriesPoint[]
  by_service: ServiceStat[]
  by_category: CategoryStat[]
  top_errors: TopError[]
}

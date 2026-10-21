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
  /** HTTP status code of the line, or null when it has none. */
  status_code: number | null
  message: string
  raw: string
}

export interface LogPage {
  items: LogEntry[]
  next_cursor: string | null
}

export interface LogCount {
  total: number
}

export interface Facets {
  services: string[]
  categories: string[]
  status_codes: number[]
}

export type Bucket = 'second' | 'minute' | 'hour' | 'day'

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

export interface LogWatch {
  id: number
  /** Path relative to the watch root of the API. */
  path: string
  interval_seconds: number
  active: boolean
  /** Import that receives every line read by this watch. */
  import_id: number
  format: string | null
  offset: number
  parsed_lines: number
  invalid_lines: number
  last_error: string | null
  created_at: string
  last_checked_at: string | null
  next_check_at: string
}

export interface LogWatchInput {
  path: string
  interval_seconds: number
  start_at_end: boolean
}

export interface WatchSettings {
  root: string
  /** The same folder on the host (GTLOG_WATCH_DIR), or null when unknown. */
  host_root: string | null
  min_interval_seconds: number
  max_interval_seconds: number
}

export interface FolderEntry {
  name: string
  /** Relative to the watch root. */
  path: string
  is_dir: boolean
  size: number | null
  modified_at: string
}

export interface Folder {
  path: string
  parent: string | null
  entries: FolderEntry[]
}

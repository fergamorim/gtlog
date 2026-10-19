// Formatters are created once: Intl constructors are expensive and the table formats thousands of rows.
const LOCALE = 'pt-BR'

const dateTimeMs = new Intl.DateTimeFormat(LOCALE, {
  day: '2-digit', month: '2-digit', year: 'numeric',
  hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3,
})
const dateTime = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'short', timeStyle: 'short' })
const shortDate = new Intl.DateTimeFormat(LOCALE, { day: '2-digit', month: '2-digit' })
const shortDateHour = new Intl.DateTimeFormat(LOCALE, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
const integer = new Intl.NumberFormat(LOCALE)
const compact = new Intl.NumberFormat(LOCALE, { notation: 'compact', maximumFractionDigits: 1 })
const percent = new Intl.NumberFormat(LOCALE, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 2 })
const relative = new Intl.RelativeTimeFormat(LOCALE, { numeric: 'auto' })

function toDate(value: string | number | Date): Date {
  return value instanceof Date ? value : new Date(value)
}

/** "05/10/2026, 17:46:57,350" (local time). */
export const formatTimestamp = (value: string) => dateTimeMs.format(toDate(value))
/** "05/10/2026, 17:46". */
export const formatDateTime = (value: string) => dateTime.format(toDate(value))
export const formatNumber = (value: number) => integer.format(value)
export const formatCompact = (value: number) => compact.format(value)
export const formatPercent = (ratio: number) => percent.format(Number.isFinite(ratio) ? ratio : 0)

/** Axis label for a time bucket: "05/10" (day) or "05/10, 17:00" (hour). */
export function formatBucket(value: string, bucket: 'hour' | 'day'): string {
  return bucket === 'day' ? shortDate.format(toDate(value)) : shortDateHour.format(toDate(value))
}

/** "3 dias e 4 h", "2 h e 15 min", "45 s". */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—'
  const s = Math.round(ms / 1000)
  const days = Math.floor(s / 86_400)
  const hours = Math.floor((s % 86_400) / 3600)
  const minutes = Math.floor((s % 3600) / 60)
  if (days > 0) return hours ? `${days} ${days === 1 ? 'dia' : 'dias'} e ${hours} h` : `${days} ${days === 1 ? 'dia' : 'dias'}`
  if (hours > 0) return minutes ? `${hours} h e ${minutes} min` : `${hours} h`
  if (minutes > 0) return `${minutes} min`
  return `${s} s`
}

/** "há 5 minutos", "ontem". */
export function formatRelative(value: string, now = Date.now()): string {
  const diff = (toDate(value).getTime() - now) / 1000
  const abs = Math.abs(diff)
  if (abs < 60) return relative.format(Math.round(diff), 'second')
  if (abs < 3600) return relative.format(Math.round(diff / 60), 'minute')
  if (abs < 86_400) return relative.format(Math.round(diff / 3600), 'hour')
  return relative.format(Math.round(diff / 86_400), 'day')
}

/** ISO (UTC) -> value for <input type="datetime-local"> in local time. */
export function isoToLocalInput(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** <input type="datetime-local"> value (local time) -> ISO (UTC). */
export function localInputToIso(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1).replace('.', ',')} KB`
  return `${(bytes / 1024 ** 2).toFixed(1).replace('.', ',')} MB`
}

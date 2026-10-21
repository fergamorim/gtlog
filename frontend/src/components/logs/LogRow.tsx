import { memo, type KeyboardEvent } from 'react'
import type { LogEntry } from '../../api/types'
import { formatTimestamp } from '../../lib/format'
import { HttpStatus } from '../ui/HttpStatus'
import { LevelBadge } from '../ui/LevelBadge'

interface RowProps {
  entry: LogEntry
  index: number
  /** Offset inside the virtual body, in px. */
  start: number
  active: boolean
  onOpen: (id: number) => void
}

function openOnKey(event: KeyboardEvent, open: () => void) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    open()
  }
}

/** Fixed-height table row; memoized so scrolling only renders rows entering the viewport. */
export const LogRow = memo(function LogRow({ entry, index, start, active, onOpen }: RowProps) {
  const open = () => onOpen(entry.id)
  return (
    <div
      role="row"
      aria-rowindex={index + 2}
      aria-current={active || undefined}
      tabIndex={0}
      data-index={index}
      className={`log-row log-row--${entry.level}${active ? ' log-row--active' : ''}`}
      style={{ transform: `translateY(${start}px)` }}
      onClick={open}
      onKeyDown={(event) => openOnKey(event, open)}
    >
      <span role="cell" className="cell cell--time">
        <time dateTime={entry.timestamp}>{formatTimestamp(entry.timestamp)}</time>
      </span>
      <span role="cell" className="cell"><LevelBadge level={entry.level} /></span>
      <span role="cell" className="cell"><HttpStatus code={entry.status_code} /></span>
      <span role="cell" className="cell">{entry.service ?? '—'}</span>
      <span role="cell" className="cell cell--muted">{entry.category ?? '—'}</span>
      <span role="cell" className="cell cell--msg" title={entry.message}>{entry.message}</span>
    </div>
  )
})

/** Card layout used below 700px: same data, stacked, fixed height. */
export const LogCard = memo(function LogCard({ entry, index, start, active, onOpen }: RowProps) {
  const open = () => onOpen(entry.id)
  return (
    <div
      role="listitem"
      tabIndex={0}
      data-index={index}
      aria-current={active || undefined}
      className={`log-card${active ? ' log-card--active' : ''}`}
      style={{ transform: `translateY(${start}px)` }}
      onClick={open}
      onKeyDown={(event) => openOnKey(event, open)}
    >
      <span className="log-card__top">
        <span className="log-card__badges">
          <LevelBadge level={entry.level} />
          {entry.status_code != null && <HttpStatus code={entry.status_code} />}
        </span>
        <time className="log-card__time" dateTime={entry.timestamp}>{formatTimestamp(entry.timestamp)}</time>
      </span>
      <span className="log-card__meta">
        {entry.service ?? 'sem serviço'} · {entry.category ?? 'sem categoria'}
      </span>
      <span className="log-card__msg">{entry.message}</span>
    </div>
  )
})

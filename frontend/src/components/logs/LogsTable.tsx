import { useVirtualizer } from '@tanstack/react-virtual'
import { useEffect, useMemo, useRef, type KeyboardEvent } from 'react'
import type { LogEntry } from '../../api/types'
import { Icon } from '../ui/Icon'
import { LogCard, LogRow } from './LogRow'

const ROW_HEIGHT = 40
const CARD_HEIGHT = 112
const HEADER_HEIGHT = 40
/** Start loading the next page when this many rows remain below the viewport. */
const PREFETCH_ROWS = 60

interface LogsTableProps {
  rows: LogEntry[]
  compact: boolean
  activeId: number | null
  onOpen: (id: number) => void
  hasNextPage: boolean
  isFetchingNextPage: boolean
  nextPageError: boolean
  fetchNextPage: () => void
  /** Changes when filters change: the list scrolls back to the top. */
  resetKey: string
  stale: boolean
}

export function LogsTable(props: LogsTableProps) {
  const { rows, compact, activeId, onOpen, hasNextPage, isFetchingNextPage, nextPageError, fetchNextPage, resetKey, stale } = props
  const scrollRef = useRef<HTMLDivElement>(null)
  const headerOffset = compact ? 0 : HEADER_HEIGHT

  // Fixed row sizes (no DOM measuring) keep scrolling smooth with 100k+ rows loaded.
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => (compact ? CARD_HEIGHT : ROW_HEIGHT),
    getItemKey: (index) => rows[index].id,
    overscan: 12,
    scrollMargin: headerOffset,
    scrollPaddingStart: headerOffset,
  })

  const items = virtualizer.getVirtualItems()
  const lastIndex = items.length ? items[items.length - 1].index : -1

  useEffect(() => {
    if (lastIndex >= rows.length - PREFETCH_ROWS && hasNextPage && !isFetchingNextPage && !nextPageError) fetchNextPage()
  }, [lastIndex, rows.length, hasNextPage, isFetchingNextPage, nextPageError, fetchNextPage])

  useEffect(() => {
    virtualizer.measure()
  }, [compact, virtualizer])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0
  }, [resetKey])

  // Keep the record opened in the drawer visible (e.g. when using Anterior/Próximo).
  const activeIndex = useMemo(() => (activeId == null ? -1 : rows.findIndex((row) => row.id === activeId)), [rows, activeId])
  useEffect(() => {
    if (activeIndex >= 0) virtualizer.scrollToIndex(activeIndex, { align: 'auto' })
  }, [activeIndex, virtualizer])

  // Arrow keys move focus between rows, scrolling virtualized rows into the DOM first.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    const current = (event.target as HTMLElement).closest<HTMLElement>('[data-index]')
    if (!current) return
    event.preventDefault()
    const next = Number(current.dataset.index) + (event.key === 'ArrowDown' ? 1 : -1)
    if (next < 0 || next >= rows.length) return
    virtualizer.scrollToIndex(next, { align: 'auto' })
    requestAnimationFrame(() => scrollRef.current?.querySelector<HTMLElement>(`[data-index="${next}"]`)?.focus())
  }

  const Item = compact ? LogCard : LogRow

  return (
    <div
      ref={scrollRef}
      className={`logs__scroll logs__grid${stale ? ' logs__scroll--stale' : ''}`}
      role={compact ? 'list' : 'table'}
      aria-label="Registros de log"
      aria-busy={stale || isFetchingNextPage}
      onKeyDown={onKeyDown}
    >
      {!compact && (
        <div role="rowgroup">
          <div role="row" aria-rowindex={1} className="logs__header">
            <span role="columnheader">Data/hora</span>
            <span role="columnheader">Nível</span>
            <span role="columnheader">Código</span>
            <span role="columnheader">Serviço</span>
            <span role="columnheader">Categoria</span>
            <span role="columnheader">Mensagem</span>
          </div>
        </div>
      )}
      <div role={compact ? undefined : 'rowgroup'} className="logs__body" style={{ height: virtualizer.getTotalSize() }}>
        {items.map((item) => (
          <Item
            key={item.key}
            entry={rows[item.index]}
            index={item.index}
            start={item.start - headerOffset}
            active={rows[item.index].id === activeId}
            onOpen={onOpen}
          />
        ))}
      </div>
      <ListFooter
        loading={isFetchingNextPage}
        error={nextPageError}
        hasMore={hasNextPage}
        count={rows.length}
        onRetry={fetchNextPage}
      />
    </div>
  )
}

interface FooterProps {
  loading: boolean
  error: boolean
  hasMore: boolean
  count: number
  onRetry: () => void
}

function ListFooter({ loading, error, hasMore, count, onRetry }: FooterProps) {
  if (error) {
    return (
      <div className="log-footer log-footer--error" role="alert">
        <Icon name="alert" /> Erro ao carregar mais registros.
        <button type="button" className="btn btn--sm" onClick={onRetry}>Tentar novamente</button>
      </div>
    )
  }
  if (loading || hasMore) {
    return (
      <div className="log-footer" role="status">
        <span className="spinner" aria-hidden="true" /> Carregando mais…
      </div>
    )
  }
  return <div className="log-footer">Fim dos resultados · {count.toLocaleString('pt-BR')} registros</div>
}

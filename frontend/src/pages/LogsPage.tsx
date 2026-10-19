import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useFilterParams, useLogs, useStats } from '../api/queries'
import { FilterBar } from '../components/filters/FilterBar'
import { LogDetailDrawer } from '../components/logs/LogDetailDrawer'
import { LogsSkeleton } from '../components/logs/LogsSkeleton'
import { LogsTable } from '../components/logs/LogsTable'
import { EmptyState, ErrorState } from '../components/ui/StateViews'
import { COMPACT_QUERY, useMediaQuery } from '../hooks/useMediaQuery'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { countActiveFilters, type FilterKey, type LogFilters } from '../lib/filters'
import { formatNumber } from '../lib/format'

const LOG_FILTER_KEYS: FilterKey[] = ['q', 'level', 'start', 'end', 'service', 'category', 'importId']

export function LogsPage() {
  const { filters, setFilters, clearFilters } = useUrlFilters()
  const [params, setParams] = useSearchParams()
  const compact = useMediaQuery(COMPACT_QUERY)
  const resetKey = useFilterParams(filters)

  const logs = useLogs(filters)
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isFetchNextPageError } = logs
  const rows = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data])

  // `log` param = record open in the drawer, so the detail view is shareable too.
  const selectedId = Number(params.get('log')) || null
  const selectedIndex = useMemo(() => (selectedId == null ? -1 : rows.findIndex((r) => r.id === selectedId)), [rows, selectedId])

  const setSelected = useCallback(
    (id: number | null) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (id == null) next.delete('log')
          else next.set('log', String(id))
          return next
        },
        { replace: true },
      ),
    [setParams],
  )

  const loadMore = useCallback(() => {
    fetchNextPage()
  }, [fetchNextPage])

  const applyFilter = (patch: Partial<LogFilters>) => {
    setSelected(null)
    setFilters(patch)
  }

  const activeFilters = countActiveFilters(filters)
  const stale = logs.isPlaceholderData

  let body
  if (logs.isPending) {
    body = <LogsSkeleton />
  } else if (logs.isError && !rows.length) {
    body = <ErrorState error={logs.error} title="Não foi possível carregar os logs" onRetry={() => logs.refetch()} retrying={logs.isFetching} />
  } else if (!rows.length) {
    body = (
      <EmptyState
        title="Nenhum log encontrado"
        icon="search"
        text={activeFilters ? 'Nenhum registro corresponde aos filtros aplicados. Ajuste ou limpe os filtros.' : 'Ainda não há logs. Importe um arquivo para começar.'}
      >
        {activeFilters ? (
          <button type="button" className="btn btn--primary" onClick={() => clearFilters()}>Limpar filtros</button>
        ) : (
          <Link to="/importar" className="btn btn--primary">Importar arquivo</Link>
        )}
      </EmptyState>
    )
  } else {
    body = (
      <LogsTable
        rows={rows}
        compact={compact}
        activeId={selectedId}
        onOpen={setSelected}
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        nextPageError={isFetchNextPageError}
        fetchNextPage={loadMore}
        resetKey={resetKey}
        stale={stale}
      />
    )
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Logs</h1>
          <p>Consulte, filtre e inspecione os registros importados.</p>
        </div>
      </div>

      <FilterBar filters={filters} onChange={applyFilter} onClear={() => clearFilters()} keys={LOG_FILTER_KEYS} />

      <section className="card logs-card" aria-label="Resultados">
        <ResultSummary filters={filters} loaded={rows.length} hasMore={hasNextPage} />
        <div className={`progress-line${stale || (logs.isFetching && !isFetchingNextPage) ? ' progress-line--active' : ''}`} aria-hidden="true" />
        {body}
      </section>

      {selectedId != null && (
        <LogDetailDrawer
          id={selectedId}
          entry={selectedIndex >= 0 ? rows[selectedIndex] : undefined}
          onClose={() => setSelected(null)}
          onPrev={selectedIndex > 0 ? () => setSelected(rows[selectedIndex - 1].id) : undefined}
          onNext={selectedIndex >= 0 && selectedIndex < rows.length - 1 ? () => setSelected(rows[selectedIndex + 1].id) : undefined}
          onFilter={applyFilter}
        />
      )}
    </>
  )
}

/** "1.234 registros · 200 carregados". The total comes from /stats (same filters) and is optional. */
function ResultSummary({ filters, loaded, hasMore }: { filters: LogFilters; loaded: number; hasMore: boolean }) {
  const stats = useStats(filters)
  const total = stats.isPlaceholderData ? undefined : stats.data?.total

  return (
    <div className="logs__summary" aria-live="polite">
      <span>
        {total != null ? (
          <><strong>{formatNumber(total)}</strong> {total === 1 ? 'registro' : 'registros'}</>
        ) : stats.isError ? (
          <>Total indisponível</>
        ) : (
          <>Calculando total…</>
        )}
      </span>
      <span>
        {formatNumber(loaded)} carregados{hasMore ? ' · role para carregar mais' : ''}
      </span>
    </div>
  )
}

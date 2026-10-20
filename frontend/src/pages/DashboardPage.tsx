import { useMemo, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useStats } from '../api/queries'
import { CategoriesChart, ServicesChart } from '../components/dashboard/RankingCharts'
import { KpiTiles } from '../components/dashboard/KpiTiles'
import { LevelDistribution } from '../components/dashboard/LevelDistribution'
import { TimeseriesChart } from '../components/dashboard/TimeseriesChart'
import { TopErrors } from '../components/dashboard/TopErrors'
import { FilterBar } from '../components/filters/FilterBar'
import { EmptyState, ErrorState } from '../components/ui/StateViews'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { countActiveFilters, DASHBOARD_FILTER_KEYS, filtersSearch, messageToQuery, pickFilters, type LogFilters } from '../lib/filters'
import { ERROR_LEVELS } from '../lib/levels'

const BUCKET_MS = { hour: 3_600_000, day: 86_400_000 }

export function DashboardPage() {
  const { filters, setFilters, clearFilters } = useUrlFilters()
  const stats = useStats(filters, DASHBOARD_FILTER_KEYS)
  const navigate = useNavigate()
  const base = useMemo(() => pickFilters(filters, DASHBOARD_FILTER_KEYS), [filters])

  /** Drill-down: the logs page opens with the dashboard filters plus `patch`. */
  const logsHref = (patch: Partial<LogFilters>) => `/logs${filtersSearch({ ...base, ...patch })}`
  const openLogs = (patch: Partial<LogFilters>) => navigate(logsHref(patch))
  const clearDashboard = () => clearFilters(DASHBOARD_FILTER_KEYS)
  const active = countActiveFilters(filters, DASHBOARD_FILTER_KEYS)

  let body: ReactNode
  if (stats.isPending) {
    body = <DashboardSkeleton />
  } else if (stats.isError && !stats.data) {
    body = <ErrorState error={stats.error} title="Não foi possível carregar o dashboard" onRetry={() => stats.refetch()} retrying={stats.isFetching} />
  } else if (stats.data.total === 0) {
    body = (
      <EmptyState
        title="Nenhum log no período"
        icon="chart"
        text={active ? 'Não há registros para os filtros selecionados.' : 'Importe um arquivo de log para ver os indicadores.'}
      >
        {active ? (
          <button type="button" className="btn btn--primary" onClick={clearDashboard}>Limpar filtros</button>
        ) : (
          <Link to="/importar" className="btn btn--primary">Importar arquivo</Link>
        )}
      </EmptyState>
    )
  } else {
    const data = stats.data
    body = (
      <div className={`stack${stats.isPlaceholderData ? ' is-stale' : ''}`} aria-busy={stats.isFetching}>
        <KpiTiles stats={data} errorsHref={logsHref({ level: ERROR_LEVELS })} />
        <div className="dash-grid">
          <Panel
            className="span-2"
            title="Volume ao longo do tempo"
            hint={`Por ${data.bucket === 'hour' ? 'hora' : 'dia'} · clique em um ponto para abrir os logs`}
          >
            <TimeseriesChart
              data={data.timeseries}
              bucket={data.bucket}
              onSelectBucket={(start) =>
                openLogs({ start, end: new Date(Date.parse(start) + BUCKET_MS[data.bucket]).toISOString() })
              }
            />
          </Panel>
          <Panel title="Distribuição por nível" hint="Clique para filtrar">
            <LevelDistribution counts={data.by_level} total={data.total} onSelect={(level) => openLogs({ level: [level] })} />
          </Panel>
          <Panel title="Top serviços" hint="Erros em destaque">
            {data.by_service.length ? (
              <ServicesChart data={data.by_service} onSelect={(service) => openLogs({ service: [service] })} />
            ) : (
              <EmptyState title="Sem serviços identificados" />
            )}
          </Panel>
          <Panel title="Top categorias">
            {data.by_category.length ? (
              <CategoriesChart data={data.by_category} onSelect={(category) => openLogs({ category: [category] })} />
            ) : (
              <EmptyState title="Sem categorias identificadas" />
            )}
          </Panel>
          <Panel title="Erros mais frequentes" hint="ERROR e CRITICAL, mensagens agrupadas">
            {data.top_errors.length ? (
              <TopErrors items={data.top_errors} hrefFor={(message) => logsHref({ q: messageToQuery(message), level: ERROR_LEVELS })} />
            ) : (
              <EmptyState title="Nenhum erro no período" icon="check" />
            )}
          </Panel>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Visão geral do volume, níveis e principais erros.</p>
        </div>
        {stats.isFetching && !stats.isPending && (
          <span className="card__hint inline-status" role="status"><span className="spinner" aria-hidden="true" /> Atualizando…</span>
        )}
      </div>
      <FilterBar filters={filters} onChange={setFilters} onClear={clearDashboard} keys={DASHBOARD_FILTER_KEYS} />
      {body}
    </>
  )
}

function Panel({ title, hint, className, children }: { title: string; hint?: string; className?: string; children: ReactNode }) {
  return (
    <section className={`card${className ? ` ${className}` : ''}`} aria-label={title}>
      <div className="card__head">
        <h2 className="card__title">{title}</h2>
        {hint && <span className="card__hint">{hint}</span>}
      </div>
      <div className="card__body">{children}</div>
    </section>
  )
}

function DashboardSkeleton() {
  return (
    <div role="status" aria-label="Carregando dashboard" className="stack">
      <div className="kpis">
        {[0, 1, 2, 3].map((i) => (
          <div className="card kpi" key={i} aria-hidden="true">
            <span className="skeleton" style={{ height: 12, width: '50%' }} />
            <span className="skeleton" style={{ height: 30, width: '70%', marginTop: 6 }} />
          </div>
        ))}
      </div>
      <div className="card card__body" aria-hidden="true">
        <span className="skeleton skeleton--chart" />
      </div>
      <span className="sr-only">Carregando dashboard…</span>
    </div>
  )
}

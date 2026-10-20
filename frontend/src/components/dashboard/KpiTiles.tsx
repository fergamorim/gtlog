import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Stats } from '../../api/types'
import { formatDateTime, formatDuration, formatNumber, formatPercent } from '../../lib/format'

interface KpiTilesProps {
  stats: Stats
  /** Link to the logs page showing only ERROR + CRITICAL. */
  errorsHref: string
}

/** Above this error rate the KPI is highlighted. */
const HIGH_ERROR_RATE = 0.05

export function KpiTiles({ stats, errorsHref }: KpiTilesProps) {
  const errors = stats.by_level.ERROR + stats.by_level.CRITICAL
  const first = stats.first_timestamp
  const last = stats.last_timestamp
  const span = first && last ? Date.parse(last) - Date.parse(first) : NaN

  return (
    <section className="kpis" aria-label="Indicadores">
      <Kpi label="Total de logs" value={formatNumber(stats.total)} sub="registros no filtro atual" />
      <Kpi
        label="Erros + críticos"
        value={formatNumber(errors)}
        danger={errors > 0}
        sub={
          <>
            ERROR {formatNumber(stats.by_level.ERROR)} · CRITICAL {formatNumber(stats.by_level.CRITICAL)}
            {errors > 0 && <> · <Link to={errorsHref}>ver</Link></>}
          </>
        }
      />
      <Kpi
        label="Taxa de erro"
        value={formatPercent(stats.error_rate)}
        danger={stats.error_rate >= HIGH_ERROR_RATE}
        sub="(ERROR + CRITICAL) / total"
      />
      <Kpi
        label="Período coberto"
        value={Number.isFinite(span) ? formatDuration(span) : '—'}
        sub={first && last ? `${formatDateTime(first)} → ${formatDateTime(last)}` : 'sem registros'}
      />
    </section>
  )
}

function Kpi({ label, value, sub, danger }: { label: string; value: string; sub: ReactNode; danger?: boolean }) {
  return (
    <div className="card kpi">
      <span className="kpi__label">{label}</span>
      <span className={`kpi__value${danger ? ' kpi__value--danger' : ''}`}>{value}</span>
      <span className="kpi__sub">{sub}</span>
    </div>
  )
}

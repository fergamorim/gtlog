import { useMemo, useState } from 'react'
import { errorMessage } from '../../api/client'
import { useStats } from '../../api/queries'
import { DASHBOARD_FILTER_KEYS, type LogFilters } from '../../lib/filters'
import { dayRange, formatDay, formatNumber, shiftDay, utcDay } from '../../lib/format'
import { Icon } from '../ui/Icon'
import { EmptyState } from '../ui/StateViews'
import { TimeseriesChart } from './TimeseriesChart'

interface HourlyVolumeProps {
  /** Dashboard filters; the chosen day replaces their period. */
  filters: LogFilters
  /** Data bounds of the dashboard, used for the default day and the picker limits. */
  firstTimestamp: string
  lastTimestamp: string
  onSelectHour: (start: string, end: string) => void
}

const HOUR_MS = 3_600_000

/** The volume chart for one chosen day (UTC), one point per hour. Defaults to the last day with logs. */
export function HourlyVolume({ filters, firstTimestamp, lastTimestamp, onSelectHour }: HourlyVolumeProps) {
  const minDay = utcDay(firstTimestamp)
  const maxDay = utcDay(lastTimestamp)
  const [picked, setPicked] = useState<string | null>(null)
  // A pick outside the current data (filters changed) falls back to the last day.
  const day = picked && picked >= minDay && picked <= maxDay ? picked : maxDay
  const dayFilters = useMemo(() => ({ ...filters, ...dayRange(day) }), [filters, day])
  const stats = useStats(dayFilters, DASHBOARD_FILTER_KEYS, 'hour')

  return (
    <>
      <div className="day-picker" role="group" aria-label="Dia exibido por hora">
        <button
          type="button"
          className="btn btn--sm btn--icon"
          onClick={() => setPicked(shiftDay(day, -1))}
          disabled={day <= minDay}
          aria-label="Dia anterior"
        >
          <Icon name="chevronLeft" />
        </button>
        <input
          type="date"
          className="input"
          value={day}
          min={minDay}
          max={maxDay}
          required
          onChange={(e) => e.target.value && setPicked(e.target.value)}
          aria-label="Dia"
        />
        <button
          type="button"
          className="btn btn--sm btn--icon"
          onClick={() => setPicked(shiftDay(day, 1))}
          disabled={day >= maxDay}
          aria-label="Próximo dia"
        >
          <Icon name="chevronRight" />
        </button>
        <span className="card__hint" aria-live="polite">
          {stats.data ? `${formatNumber(stats.data.total)} logs em ${formatDay(day)}` : `Carregando ${formatDay(day)}…`}
        </span>
      </div>
      {stats.isError && !stats.data ? (
        <p className="field__error" role="alert">Não foi possível carregar o dia: {errorMessage(stats.error)}</p>
      ) : stats.data && stats.data.total === 0 ? (
        <EmptyState title="Nenhum log neste dia" text="Escolha outro dia no seletor acima." icon="chart" />
      ) : (
        <div className={stats.isPlaceholderData || !stats.data ? 'is-stale' : undefined}>
          <TimeseriesChart
            data={stats.data?.timeseries ?? []}
            bucket="hour"
            singleDay
            onSelectBucket={(start) => onSelectHour(start, new Date(Date.parse(start) + HOUR_MS).toISOString())}
          />
        </div>
      )}
    </>
  )
}

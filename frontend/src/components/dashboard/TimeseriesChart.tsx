import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts'
import { LEVELS, type Bucket, type Level, type TimeseriesPoint } from '../../api/types'
import { formatBucket, formatCompact, formatDateTime, formatNumber, spansYears } from '../../lib/format'
import { LEVEL_META, LEVELS_BY_SEVERITY, levelVars } from '../../lib/levels'
import { ChartTooltip } from './ChartTooltip'

interface TimeseriesChartProps {
  data: TimeseriesPoint[]
  bucket: Bucket
  /** Opens the logs of one bucket. */
  onSelectBucket: (bucketStart: string) => void
}

/** Most severe at the bottom of the stack so errors sit on the baseline and stay readable. */
const STACK_ORDER = LEVELS_BY_SEVERITY

export function TimeseriesChart({ data, bucket, onSelectBucket }: TimeseriesChartProps) {
  const [hidden, setHidden] = useState<Set<Level>>(() => new Set())
  const withYear = bucket === 'day' && spansYears(data.map((point) => point.bucket))
  const toggle = (level: Level) =>
    setHidden((current) => {
      const next = new Set(current)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })

  return (
    <>
      <div className="legend" role="group" aria-label="Exibir níveis no gráfico">
        {LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            className="chip"
            style={levelVars(level)}
            aria-pressed={!hidden.has(level)}
            onClick={() => toggle(level)}
          >
            <span className="level-dot" aria-hidden="true" />
            {level}
          </button>
        ))}
      </div>
      <div className="chart" role="img" aria-label={`Volume de logs por nível, agrupado por ${bucket === 'hour' ? 'hora' : 'dia'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 12, right: 8, bottom: 0, left: 0 }}
            onClick={(state) => {
              if (state?.activeLabel) onSelectBucket(String(state.activeLabel))
            }}
            style={{ cursor: 'pointer' }}
          >
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="bucket"
              tickFormatter={(value: string) => formatBucket(value, bucket, withYear)}
              stroke="var(--chart-axis)"
              tick={{ fill: 'var(--chart-axis)' }}
              tickLine={false}
              minTickGap={28}
            />
            <YAxis
              tickFormatter={formatCompact}
              stroke="var(--chart-axis)"
              tick={{ fill: 'var(--chart-axis)' }}
              tickLine={false}
              axisLine={false}
              width={48}
              allowDecimals={false}
            />
            <Tooltip content={<SeriesTooltip bucket={bucket} hidden={hidden} />} cursor={{ stroke: 'var(--border-strong)' }} />
            {STACK_ORDER.map((level) => (
              <Area
                key={level}
                type="monotone"
                dataKey={level}
                name={level}
                stackId="levels"
                hide={hidden.has(level)}
                stroke={LEVEL_META[level].color}
                fill={LEVEL_META[level].color}
                fillOpacity={0.35}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary className="card__hint">Ver dados em tabela</summary>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Intervalo</th>
                {LEVELS.map((level) => <th scope="col" className="num" key={level}>{level}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.map((point) => (
                <tr key={point.bucket}>
                  <td>{formatDateTime(point.bucket)}</td>
                  {LEVELS.map((level) => <td className="num" key={level}>{formatNumber(point[level])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

function SeriesTooltip({ active, payload, label, bucket, hidden }: TooltipProps<number, string> & { bucket: Bucket; hidden: Set<Level> }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload as TimeseriesPoint
  const visible = LEVELS_BY_SEVERITY.filter((level) => !hidden.has(level))
  const total = visible.reduce((sum, level) => sum + point[level], 0)
  return (
    <ChartTooltip
      title={bucket === 'hour' ? formatDateTime(String(label)) : formatBucket(String(label), 'day', true)}
      rows={[
        ...visible.map((level) => ({ key: level, label: level, value: formatNumber(point[level]), color: LEVEL_META[level].color })),
        { key: 'total', label: 'Total', value: formatNumber(total) },
      ]}
      hint="Clique para ver os logs deste intervalo"
    />
  )
}

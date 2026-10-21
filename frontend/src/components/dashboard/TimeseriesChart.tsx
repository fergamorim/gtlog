import { useState } from 'react'
import { Area, AreaChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts'
import { LEVELS, type Bucket, type Level, type TimeseriesPoint } from '../../api/types'
import { BUCKET_LABEL, formatBucket, formatBucketTitle, formatCompact, formatHour, formatNumber, spansYears } from '../../lib/format'
import { LEVEL_META, LEVELS_BY_SEVERITY, levelVars } from '../../lib/levels'
import { ChartTooltip } from './ChartTooltip'

interface TimeseriesChartProps {
  data: TimeseriesPoint[]
  bucket: Bucket
  /** Opens the logs of one bucket. */
  onSelectBucket: (bucketStart: string) => void
  /** The points cover a single day: label the axis with the hour only. */
  singleDay?: boolean
  /** Dragging across the chart selects [first, last] buckets to zoom into; without it, a drag is a click. */
  onZoom?: (firstBucket: string, lastBucket: string) => void
}

/** Most severe at the bottom of the stack so errors sit on the baseline and stay readable. */
const STACK_ORDER = LEVELS_BY_SEVERITY

export function TimeseriesChart({ data, bucket, onSelectBucket, singleDay = false, onZoom }: TimeseriesChartProps) {
  const [hidden, setHidden] = useState<Set<Level>>(() => new Set())
  // Bucket labels where a drag started and where it is now (ISO strings sort chronologically).
  const [drag, setDrag] = useState<{ from: string; to: string } | null>(null)
  const finishDrag = () => {
    if (!drag) return
    setDrag(null)
    const [first, last] = drag.from <= drag.to ? [drag.from, drag.to] : [drag.to, drag.from]
    if (onZoom && first !== last) onZoom(first, last)
    else onSelectBucket(drag.from)
  }
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
      <div className="chart" role="img" aria-label={`Volume de logs por nível, agrupado por ${BUCKET_LABEL[bucket]}`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 12, right: 8, bottom: 0, left: 0 }}
            onMouseDown={(state) => {
              if (state?.activeLabel) setDrag({ from: String(state.activeLabel), to: String(state.activeLabel) })
            }}
            onMouseMove={(state) => {
              if (drag && state?.activeLabel) setDrag({ ...drag, to: String(state.activeLabel) })
            }}
            onMouseUp={finishDrag}
            onMouseLeave={() => setDrag(null)}
            style={{ cursor: onZoom ? 'crosshair' : 'pointer', userSelect: 'none' }}
          >
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey="bucket"
              tickFormatter={(value: string) => (singleDay ? formatHour(value) : formatBucket(value, bucket, withYear))}
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
            {drag && drag.from !== drag.to && (
              <ReferenceArea x1={drag.from} x2={drag.to} fill="var(--accent)" fillOpacity={0.12} stroke="var(--accent)" strokeOpacity={0.4} />
            )}
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
                  <td>{formatBucketTitle(point.bucket, bucket)}</td>
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
      title={formatBucketTitle(String(label), bucket)}
      rows={[
        ...visible.map((level) => ({ key: level, label: level, value: formatNumber(point[level]), color: LEVEL_META[level].color })),
        { key: 'total', label: 'Total', value: formatNumber(total) },
      ]}
      hint="Clique para ver os logs deste intervalo"
    />
  )
}

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from 'recharts'
import type { CategoryStat, ServiceStat } from '../../api/types'
import { formatCompact, formatNumber, formatPercent } from '../../lib/format'
import { LEVEL_META } from '../../lib/levels'
import { ChartTooltip } from './ChartTooltip'

const ROW_HEIGHT = 34
const chartHeight = (rows: number) => Math.max(rows * ROW_HEIGHT + 24, 120)

const axisProps = {
  stroke: 'var(--chart-axis)',
  tick: { fill: 'var(--chart-axis)' },
  tickLine: false,
} as const

/* ------------------------------ Services -------------------------------- */

type ServiceRow = ServiceStat & { others: number }

/** Stacked horizontal bars: errors (ERROR color) + other levels (neutral), sorted by total. */
export function ServicesChart({ data, onSelect }: { data: ServiceStat[]; onSelect: (service: string) => void }) {
  const rows: ServiceRow[] = [...data].sort((a, b) => b.total - a.total).map((s) => ({ ...s, others: s.total - s.errors }))
  return (
    <div className="chart" style={{ height: chartHeight(rows.length) }} role="img" aria-label="Volume de logs por serviço, com erros destacados">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 0 }} barCategoryGap={8}>
          <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
          <XAxis type="number" tickFormatter={formatCompact} {...axisProps} axisLine={false} />
          <YAxis type="category" dataKey="service" width={104} {...axisProps} />
          <Tooltip content={<ServiceTooltip />} cursor={{ fill: 'var(--surface-hover)' }} />
          <Bar
            dataKey="errors"
            name="Erros"
            stackId="s"
            fill={LEVEL_META.ERROR.color}
            cursor="pointer"
            isAnimationActive={false}
            onClick={(row: ServiceRow) => onSelect(row.service)}
          />
          <Bar
            dataKey="others"
            name="Demais níveis"
            stackId="s"
            fill="var(--chart-neutral)"
            radius={[0, 4, 4, 0]}
            cursor="pointer"
            isAnimationActive={false}
            onClick={(row: ServiceRow) => onSelect(row.service)}
          >
            <LabelList dataKey="total" position="right" formatter={formatCompact} fill="var(--muted)" fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ServiceTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload as ServiceRow
  return (
    <ChartTooltip
      title={row.service}
      rows={[
        { key: 'errors', label: 'Erros (ERROR + CRITICAL)', value: formatNumber(row.errors), color: LEVEL_META.ERROR.color },
        { key: 'others', label: 'Demais níveis', value: formatNumber(row.others), color: 'var(--chart-neutral)' },
        { key: 'total', label: 'Total', value: formatNumber(row.total) },
        { key: 'rate', label: 'Taxa de erro', value: formatPercent(row.errors / Math.max(row.total, 1)) },
      ]}
      hint="Clique para ver os logs do serviço"
    />
  )
}

/* ----------------------------- Categories ------------------------------- */

export function CategoriesChart({ data, onSelect }: { data: CategoryStat[]; onSelect: (category: string) => void }) {
  const rows = [...data].sort((a, b) => b.total - a.total)
  return (
    <div className="chart" style={{ height: chartHeight(rows.length) }} role="img" aria-label="Volume de logs por categoria">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 0 }} barCategoryGap={8}>
          <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
          <XAxis type="number" tickFormatter={formatCompact} {...axisProps} axisLine={false} />
          <YAxis type="category" dataKey="category" width={120} {...axisProps} />
          <Tooltip content={<CategoryTooltip />} cursor={{ fill: 'var(--surface-hover)' }} />
          <Bar
            dataKey="total"
            name="Total"
            fill="var(--chart-accent)"
            radius={[0, 4, 4, 0]}
            cursor="pointer"
            isAnimationActive={false}
            onClick={(row: CategoryStat) => onSelect(row.category)}
          >
            <LabelList dataKey="total" position="right" formatter={formatCompact} fill="var(--muted)" fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function CategoryTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload as CategoryStat
  return (
    <ChartTooltip
      title={row.category}
      rows={[{ key: 'total', label: 'Registros', value: formatNumber(row.total), color: 'var(--chart-accent)' }]}
      hint="Clique para ver os logs da categoria"
    />
  )
}

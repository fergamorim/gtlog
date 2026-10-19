import type { ReactNode } from 'react'

export interface TooltipRow {
  key: string
  label: string
  value: string
  color?: string
}

/** Shared tooltip body for Recharts charts (styled by index.css, theme-aware). */
export function ChartTooltip({ title, rows, hint }: { title: ReactNode; rows: TooltipRow[]; hint?: string }) {
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{title}</div>
      {rows.map((row) => (
        <div className="chart-tooltip__row" key={row.key}>
          <span className="chart-tooltip__key">
            {row.color && <span className="level-dot" style={{ background: row.color }} aria-hidden="true" />}
            {row.label}
          </span>
          <span>{row.value}</span>
        </div>
      ))}
      {hint && <div className="chart-tooltip__hint">{hint}</div>}
    </div>
  )
}

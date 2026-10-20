import { LEVELS, type Level, type LevelCounts } from '../../api/types'
import { formatNumber, formatPercent } from '../../lib/format'
import { levelVars } from '../../lib/levels'

interface LevelDistributionProps {
  counts: LevelCounts
  total: number
  onSelect: (level: Level) => void
}

/** Horizontal bars (more precise than a donut) with value and share; each row opens the filtered logs. */
export function LevelDistribution({ counts, total, onSelect }: LevelDistributionProps) {
  const max = Math.max(...LEVELS.map((level) => counts[level]), 1)
  return (
    <ul className="dist">
      {LEVELS.map((level) => {
        const value = counts[level]
        return (
          <li key={level}>
            <button
              type="button"
              className="dist__item"
              style={levelVars(level)}
              onClick={() => onSelect(level)}
              aria-label={`${level}: ${formatNumber(value)} registros (${formatPercent(value / Math.max(total, 1))}). Ver logs.`}
            >
              <span className="level-badge"><span className="level-dot" aria-hidden="true" />{level}</span>
              <span className="dist__track" aria-hidden="true">
                <span className="dist__bar" style={{ width: `${(value / max) * 100}%` }} />
              </span>
              <span className="dist__value">
                <strong>{formatNumber(value)}</strong> · {formatPercent(value / Math.max(total, 1))}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

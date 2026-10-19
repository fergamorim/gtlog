import { LEVELS, type Level } from '../../api/types'
import { levelVars } from '../../lib/levels'
import { Icon } from '../ui/Icon'

interface LevelChipsProps {
  value: Level[]
  onChange: (levels: Level[]) => void
}

/** Toggle chips; none selected means "all levels". */
export function LevelChips({ value, onChange }: LevelChipsProps) {
  const toggle = (level: Level) =>
    onChange(value.includes(level) ? value.filter((l) => l !== level) : LEVELS.filter((l) => l === level || value.includes(l)))

  return (
    <div className="field">
      <span className="field__label" id="level-chips-label">Nível</span>
      <div className="chips" role="group" aria-labelledby="level-chips-label">
        {LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            className="chip"
            style={levelVars(level)}
            aria-pressed={value.includes(level)}
            onClick={() => toggle(level)}
          >
            <span className="level-dot" aria-hidden="true" />
            {level}
            <span className="chip__check"><Icon name="check" size={12} /></span>
          </button>
        ))}
      </div>
    </div>
  )
}

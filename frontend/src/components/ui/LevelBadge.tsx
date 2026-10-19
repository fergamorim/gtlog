import type { Level } from '../../api/types'
import { levelVars } from '../../lib/levels'

/** Level shown as text + colored dot, so meaning never relies on color alone. */
export function LevelBadge({ level }: { level: Level }) {
  return (
    <span className="level-badge" style={levelVars(level)}>
      <span className="level-dot" aria-hidden="true" />
      {level}
    </span>
  )
}

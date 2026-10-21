import { levelVars } from '../../lib/levels'
import { levelForStatus, statusLevels } from '../../lib/status'
import { LevelBadge } from './LevelBadge'

/** HTTP status code colored by its correlated level (dot + text); "—" when the line has no code. */
export function HttpStatus({ code }: { code: number | null }) {
  const level = levelForStatus(code)
  if (code == null || !level) return <span className="http-status http-status--none">—</span>
  return (
    <span className="http-status" style={levelVars(level)} title={`HTTP ${code} · ${level}`}>
      <span className="level-dot" aria-hidden="true" />
      {code}
    </span>
  )
}

/** Filter option: the code or class plus the level(s) it correlates to, e.g. "404 · WARNING". */
export function HttpStatusOption({ status }: { status: string }) {
  return (
    <span className="http-status-option">
      <span className="mono">{status}</span>
      <span aria-hidden="true">·</span>
      {statusLevels(status).map((level) => (
        <LevelBadge key={level} level={level} />
      ))}
    </span>
  )
}

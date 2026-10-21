import { useState } from 'react'
import { isoToLocalInput, localInputToIso } from '../../lib/format'

interface DateRangeFilterProps {
  start: string | null
  end: string | null
  onChange: (range: { start: string | null; end: string | null }) => void
}

const HOUR = 3_600_000
const PRESETS = [
  { label: '1 h', title: 'Última hora', ms: HOUR },
  { label: '24 h', title: 'Últimas 24 horas', ms: 24 * HOUR },
  { label: '7 d', title: 'Últimos 7 dias', ms: 7 * 24 * HOUR },
  { label: '30 d', title: 'Últimos 30 dias', ms: 30 * 24 * HOUR },
]

export function DateRangeFilter({ start, end, onChange }: DateRangeFilterProps) {
  const [error, setError] = useState<string | null>(null)

  const commit = (nextStart: string | null, nextEnd: string | null) => {
    if (nextStart && nextEnd && Date.parse(nextStart) >= Date.parse(nextEnd)) {
      setError('A data inicial deve ser anterior à final.')
      return
    }
    setError(null)
    onChange({ start: nextStart, end: nextEnd })
  }

  const applyPreset = (ms: number) => {
    // Round to the minute so the URL (and the query key) stays stable and readable.
    const now = Math.floor(Date.now() / 60_000) * 60_000
    commit(new Date(now - ms).toISOString(), null)
  }

  return (
    <div className="field">
      <span className="field__label" id="period-label">Período (UTC)</span>
      <div className="daterange" role="group" aria-labelledby="period-label">
        <input
          className="input"
          type="datetime-local"
          aria-label="Data inicial"
          value={isoToLocalInput(start)}
          max={isoToLocalInput(end) || undefined}
          onChange={(event) => commit(localInputToIso(event.target.value), end)}
        />
        <input
          className="input"
          type="datetime-local"
          aria-label="Data final (exclusiva)"
          value={isoToLocalInput(end)}
          min={isoToLocalInput(start) || undefined}
          onChange={(event) => commit(start, localInputToIso(event.target.value))}
        />
        <div className="presets">
          {PRESETS.map((preset) => (
            <button key={preset.label} type="button" className="btn btn--sm" title={preset.title} aria-label={preset.title} onClick={() => applyPreset(preset.ms)}>
              {preset.label}
            </button>
          ))}
          <button type="button" className="btn btn--sm btn--ghost" onClick={() => commit(null, null)} disabled={!start && !end}>
            Tudo
          </button>
        </div>
      </div>
      {error && <span className="field__error" role="alert">{error}</span>}
    </div>
  )
}

import { useState, type FormEvent } from 'react'
import { errorMessage } from '../../api/client'
import { useWatchMutations, useWatchSettings } from '../../api/queries'
import { Icon } from '../ui/Icon'
import { WatchFilePicker } from './WatchFilePicker'

type Unit = 'seconds' | 'minutes'
const UNIT_SECONDS: Record<Unit, number> = { seconds: 1, minutes: 60 }
const DEFAULT_MAX_SECONDS = 86_400

/** Starts watching a file of the API's watch folder, re-read every N seconds or minutes. */
export function WatchForm() {
  const { create } = useWatchMutations()
  const { data: settings } = useWatchSettings()
  const [path, setPath] = useState('')
  const [amount, setAmount] = useState('10')
  const [unit, setUnit] = useState<Unit>('seconds')
  const [startAtEnd, setStartAtEnd] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const [picking, setPicking] = useState(false)

  const min = settings?.min_interval_seconds ?? 1
  const max = settings?.max_interval_seconds ?? DEFAULT_MAX_SECONDS

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const value = Number(amount)
    const seconds = value * UNIT_SECONDS[unit]
    if (!path.trim()) return setLocalError('Informe o caminho do arquivo.')
    if (!Number.isInteger(value) || seconds < min || seconds > max) {
      return setLocalError(`O intervalo deve ser um número inteiro entre ${min} segundo e ${max / 3600} horas.`)
    }
    setLocalError(null)
    create.mutate(
      { path: path.trim(), interval_seconds: seconds, start_at_end: startAtEnd },
      { onSuccess: () => setPath('') },
    )
  }

  // With the host folder known (GTLOG_WATCH_DIR), the field shows the full path as the user sees it on disk.
  const hostRoot = settings?.host_root ?? null
  const display = (relative: string) => (hostRoot ? `${hostRoot}/${relative}` : relative)

  const error = localError ?? (create.isError ? errorMessage(create.error) : null)

  return (
    <form className="watch-form" onSubmit={submit} noValidate>
      <div className="field">
        <label className="field__label" htmlFor="watch-path">Arquivo</label>
        <div className="watch-form__path">
          <input
            id="watch-path"
            className="input"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder={display('live.log')}
            autoComplete="off"
            spellCheck={false}
            aria-describedby="watch-path-hint"
          />
          <button type="button" className="btn" onClick={() => setPicking(true)}>
            <Icon name="folder" /> Selecionar arquivo
          </button>
        </div>
        <span className="card__hint" id="watch-path-hint">
          {hostRoot ? (
            <>O arquivo precisa estar em <code>{hostRoot}</code>, a pasta compartilhada com a API.</>
          ) : (
            <>
              Caminho dentro da pasta compartilhada com a API: a pasta <code>samples/</code> do projeto, ou a indicada
              em <code>GTLOG_WATCH_DIR</code> ao subir o Docker.
            </>
          )}
        </span>
        {picking && (
          <WatchFilePicker
            rootLabel={hostRoot ?? 'samples'}
            onClose={() => setPicking(false)}
            onPick={(picked) => {
              setPath(display(picked))
              setLocalError(null)
              setPicking(false)
            }}
          />
        )}
      </div>
      <div className="field">
        <span className="field__label" id="watch-interval-label">Ler a cada</span>
        <div className="watch-form__interval" role="group" aria-labelledby="watch-interval-label">
          <input
            className="input"
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            aria-label="Intervalo"
          />
          <select className="select" value={unit} onChange={(e) => setUnit(e.target.value as Unit)} aria-label="Unidade do intervalo">
            <option value="seconds">segundos</option>
            <option value="minutes">minutos</option>
          </select>
        </div>
      </div>
      <label className="checkbox">
        <input type="checkbox" checked={startAtEnd} onChange={(e) => setStartAtEnd(e.target.checked)} />
        Ignorar o conteúdo atual e importar só as linhas novas
      </label>
      {error && (
        <div className="alert alert--error" role="alert">
          <Icon name="alert" />
          <span><strong>Não foi possível observar o arquivo.</strong> {error}</span>
        </div>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={create.isPending}>
          <Icon name="eye" /> {create.isPending ? 'Iniciando…' : 'Observar arquivo'}
        </button>
      </div>
    </form>
  )
}

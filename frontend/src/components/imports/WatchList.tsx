import { Link } from 'react-router-dom'
import { errorMessage } from '../../api/client'
import { useWatchMutations, useWatchSettings, useWatches } from '../../api/queries'
import type { LogWatch } from '../../api/types'
import { formatDateTime, formatInterval, formatNumber, formatRelative } from '../../lib/format'
import { Icon } from '../ui/Icon'
import { ErrorState } from '../ui/StateViews'

export function WatchList() {
  const { data, isError, error, refetch, isFetching } = useWatches()
  const { setActive, remove } = useWatchMutations()
  const hostRoot = useWatchSettings().data?.host_root

  if (isError) return <ErrorState error={error} title="Não foi possível listar as observações" onRetry={() => refetch()} retrying={isFetching} />
  if (!data?.length) return null

  const failed = setActive.error ?? remove.error
  return (
    <>
      {failed && (
        <div className="alert alert--error" role="alert">
          <Icon name="alert" />
          <span>{errorMessage(failed)}</span>
        </div>
      )}
      <ul className="import-list watch-list" aria-label="Arquivos observados">
        {data.map((watch) => (
          <li key={watch.id} className="import-item">
            <span className="import-item__name" title={hostRoot ? `${hostRoot}/${watch.path}` : watch.path}>{watch.path}</span>
            <WatchBadge watch={watch} />
            <span className="import-item__meta">
              <span>a cada {formatInterval(watch.interval_seconds)}</span>
              {watch.last_checked_at ? (
                <span>
                  lido <time dateTime={watch.last_checked_at} title={formatDateTime(watch.last_checked_at)}>{formatRelative(watch.last_checked_at)}</time>
                </span>
              ) : (
                <span>aguardando a primeira leitura</span>
              )}
              <span>{formatNumber(watch.parsed_lines)} válidas</span>
              <span>{formatNumber(watch.invalid_lines)} inválidas</span>
              {watch.format && <span>formato {watch.format}</span>}
            </span>
            {watch.last_error && <span className="import-item__error">{watch.last_error}</span>}
            <span className="import-item__links">
              <Link to={`/logs?import_id=${watch.import_id}`}>Ver logs</Link>
              <Link to={`/dashboard?import_id=${watch.import_id}`}>Dashboard</Link>
              <button
                type="button"
                className="btn btn--sm"
                onClick={() => setActive.mutate({ id: watch.id, active: !watch.active })}
                disabled={setActive.isPending}
              >
                {watch.active ? 'Pausar' : 'Retomar'}
              </button>
              <button
                type="button"
                className="btn btn--sm btn--ghost"
                onClick={() => remove.mutate(watch.id)}
                disabled={remove.isPending}
                aria-label={`Parar de observar ${watch.path}`}
              >
                Remover
              </button>
            </span>
          </li>
        ))}
      </ul>
      <p className="card__hint watch-list__hint">Remover para a observação; os logs já importados continuam disponíveis.</p>
    </>
  )
}

function WatchBadge({ watch }: { watch: LogWatch }) {
  if (!watch.active) return <span className="status-badge status-badge--PAUSED">Pausada</span>
  if (watch.last_error) {
    return (
      <span className="status-badge status-badge--FAILED">
        <Icon name="alert" size={12} /> Com erro
      </span>
    )
  }
  return (
    <span className="status-badge status-badge--DONE">
      <span className="live-dot" aria-hidden="true" /> Observando
    </span>
  )
}

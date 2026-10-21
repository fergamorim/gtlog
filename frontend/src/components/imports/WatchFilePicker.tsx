import { useState } from 'react'
import { useWatchFolder } from '../../api/queries'
import { formatBytes, formatDateTime } from '../../lib/format'
import { Drawer } from '../ui/Drawer'
import { Icon } from '../ui/Icon'
import { EmptyState, ErrorState } from '../ui/StateViews'

interface WatchFilePickerProps {
  /** Shown as the root's name, e.g. the host folder. */
  rootLabel: string
  onPick: (path: string) => void
  onClose: () => void
}

/**
 * Browses the API's watch folder. The browser's own file dialog cannot be used here: it hands the page the
 * file's contents but never its path, and the API needs a path it can keep re-reading.
 */
export function WatchFilePicker({ rootLabel, onPick, onClose }: WatchFilePickerProps) {
  const [path, setPath] = useState('')
  const { data, isPending, isError, error, refetch, isFetching } = useWatchFolder(path, true)

  return (
    <Drawer title="Selecionar arquivo" onClose={onClose}>
      <nav className="picker__crumbs" aria-label="Pasta atual">
        <button type="button" className="btn btn--sm btn--ghost" onClick={() => setPath('')} disabled={!path}>
          <Icon name="folder" size={14} /> {rootLabel}
        </button>
        {path.split('/').filter(Boolean).map((part, index, parts) => {
          const target = parts.slice(0, index + 1).join('/')
          return (
            <span key={target} className="picker__crumb">
              <span aria-hidden="true">/</span>
              <button type="button" className="btn btn--sm btn--ghost" onClick={() => setPath(target)} disabled={target === path}>
                {part}
              </button>
            </span>
          )
        })}
      </nav>

      {isPending ? (
        <p role="status" className="card__hint inline-status"><span className="spinner" aria-hidden="true" /> Carregando…</p>
      ) : isError ? (
        <ErrorState error={error} title="Não foi possível abrir a pasta" onRetry={() => refetch()} retrying={isFetching} />
      ) : !data.entries.length ? (
        <EmptyState title="Pasta vazia" text="Não há arquivos nem subpastas aqui." icon="file" />
      ) : (
        <ul className="picker__list" aria-label="Conteúdo da pasta">
          {data.parent != null && (
            <li>
              <button type="button" className="picker__item" onClick={() => setPath(data.parent ?? '')}>
                <Icon name="folder" /> <span className="picker__name">..</span>
              </button>
            </li>
          )}
          {data.entries.map((entry) => (
            <li key={entry.path}>
              <button
                type="button"
                className="picker__item"
                onClick={() => (entry.is_dir ? setPath(entry.path) : onPick(entry.path))}
                aria-label={entry.is_dir ? `Abrir pasta ${entry.name}` : `Selecionar ${entry.name}`}
              >
                <Icon name={entry.is_dir ? 'folder' : 'file'} />
                <span className="picker__name">{entry.name}</span>
                <span className="picker__meta">
                  {entry.size != null && formatBytes(entry.size)} {formatDateTime(entry.modified_at)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  )
}

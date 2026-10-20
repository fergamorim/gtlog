import { useState } from 'react'
import { ApiError } from '../../api/client'
import { useLog } from '../../api/queries'
import type { LogEntry } from '../../api/types'
import { formatTimestamp } from '../../lib/format'
import type { LogFilters } from '../../lib/filters'
import { Drawer } from '../ui/Drawer'
import { Icon } from '../ui/Icon'
import { LevelBadge } from '../ui/LevelBadge'
import { ErrorState } from '../ui/StateViews'

interface LogDetailDrawerProps {
  id: number
  /** The row when it is already loaded in the table (avoids a request). */
  entry?: LogEntry
  onClose: () => void
  onPrev?: () => void
  onNext?: () => void
  onFilter: (patch: Partial<LogFilters>) => void
}

export function LogDetailDrawer({ id, entry, onClose, onPrev, onNext, onFilter }: LogDetailDrawerProps) {
  const query = useLog(id, entry)
  // Prefer the loaded row: on a deep link the rows may arrive after the single-record request started.
  const log = entry ?? query.data

  const footer = (
    <>
      <button type="button" className="btn" onClick={onPrev} disabled={!onPrev}>
        <Icon name="chevronUp" /> Anterior
      </button>
      <button type="button" className="btn" onClick={onNext} disabled={!onNext}>
        Próximo <Icon name="chevronDown" />
      </button>
    </>
  )

  return (
    <Drawer
      title={log ? <><LevelBadge level={log.level} /> Log #{log.id}</> : `Log #${id}`}
      onClose={onClose}
      footer={footer}
      onKeyDown={(event) => {
        const target = event.target as HTMLElement
        if (target.closest('pre, input, textarea')) return
        if (event.key === 'ArrowDown' && onNext) { event.preventDefault(); onNext() }
        if (event.key === 'ArrowUp' && onPrev) { event.preventDefault(); onPrev() }
      }}
    >
      {log ? (
        <LogDetails log={log} onFilter={onFilter} />
      ) : query.isError ? (
        <ErrorState
          error={query.error}
          title={query.error instanceof ApiError && query.error.status === 404 ? 'Log não encontrado' : 'Erro ao carregar o log'}
          onRetry={() => query.refetch()}
          retrying={query.isFetching}
        />
      ) : (
        <div role="status" className="state"><span className="spinner" aria-hidden="true" /> Carregando…</div>
      )}
    </Drawer>
  )
}

function LogDetails({ log, onFilter }: { log: LogEntry; onFilter: LogDetailDrawerProps['onFilter'] }) {
  return (
    <>
      <dl className="meta-list">
        <dt>Data/hora</dt>
        <dd>
          <time dateTime={log.timestamp}>{formatTimestamp(log.timestamp)}</time>
          <div className="card__hint mono">{log.timestamp}</div>
        </dd>
        <dt>Serviço</dt>
        <dd>{log.service ?? '—'}</dd>
        <dt>Categoria</dt>
        <dd>{log.category ?? '—'}</dd>
        <dt>Importação</dt>
        <dd>#{log.import_id}</dd>
      </dl>

      <section>
        <h3 className="section-title">Mensagem</h3>
        <CodeBlock text={log.message} label="mensagem" />
      </section>
      <section>
        <h3 className="section-title">Linha original</h3>
        <CodeBlock text={log.raw} label="linha original" />
      </section>

      <section className="actions" aria-label="Filtrar a partir deste log">
        {log.service && (
          <button type="button" className="btn btn--sm" onClick={() => onFilter({ service: [log.service!] })}>
            <Icon name="filter" /> Só o serviço {log.service}
          </button>
        )}
        <button type="button" className="btn btn--sm" onClick={() => onFilter({ level: [log.level] })}>
          <Icon name="filter" /> Só nível {log.level}
        </button>
        <button type="button" className="btn btn--sm" onClick={() => onFilter({ importId: log.import_id })}>
          <Icon name="filter" /> Só a importação #{log.import_id}
        </button>
      </section>
    </>
  )
}

function CodeBlock({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div className="code-block">
      <pre tabIndex={0}>{text}</pre>
      <button type="button" className="btn btn--sm" onClick={copy} aria-label={`Copiar ${label}`}>
        <Icon name={copied ? 'check' : 'copy'} /> {copied ? 'Copiado' : 'Copiar'}
      </button>
    </div>
  )
}

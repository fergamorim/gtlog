import { Link } from 'react-router-dom'
import { useImports } from '../../api/queries'
import { formatDateTime, formatNumber, formatRelative } from '../../lib/format'
import { EmptyState, ErrorState } from '../ui/StateViews'
import { StatusBadge } from '../ui/StatusBadge'

export function ImportList() {
  const { data, isPending, isError, error, refetch, isFetching } = useImports()

  if (isPending) {
    return (
      <ul className="import-list" aria-label="Carregando importações">
        {[0, 1, 2].map((i) => (
          <li className="import-item" key={i} aria-hidden="true">
            <span className="skeleton" style={{ height: 14, width: '50%' }} />
            <span className="skeleton" style={{ height: 18, width: 80 }} />
            <span className="skeleton" style={{ height: 10, width: '70%', gridColumn: '1 / -1' }} />
          </li>
        ))}
      </ul>
    )
  }
  if (isError) return <ErrorState error={error} title="Não foi possível listar as importações" onRetry={() => refetch()} retrying={isFetching} />
  if (!data.length) return <EmptyState title="Nenhuma importação ainda" text="Os arquivos enviados aparecem aqui com status e contadores." icon="file" />

  return (
    <ul className="import-list">
      {data.map((job) => (
        <li key={job.id} className="import-item">
          <span className="import-item__name" title={job.filename}>#{job.id} · {job.filename}</span>
          <StatusBadge status={job.status} />
          <span className="import-item__meta">
            <time dateTime={job.created_at} title={formatDateTime(job.created_at)}>{formatRelative(job.created_at)}</time>
            <span>{formatNumber(job.parsed_lines)} válidas</span>
            <span>{formatNumber(job.invalid_lines)} inválidas</span>
            {job.format && <span>formato {job.format}</span>}
          </span>
          {job.status === 'FAILED' && job.error && <span className="import-item__error">{job.error}</span>}
          {job.status === 'DONE' && (
            <span className="import-item__links">
              <Link to={`/logs?import_id=${job.id}`}>Ver logs</Link>
              <Link to={`/dashboard?import_id=${job.id}`}>Dashboard</Link>
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

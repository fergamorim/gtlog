import { Link } from 'react-router-dom'
import { errorMessage } from '../../api/client'
import { useImportJob } from '../../api/queries'
import type { ImportJob } from '../../api/types'
import { formatDuration, formatNumber, formatPercent } from '../../lib/format'
import { Icon } from '../ui/Icon'
import { StatusBadge } from '../ui/StatusBadge'

/** Live progress of one import, polled every second until DONE/FAILED. */
export function ImportProgress({ jobId }: { jobId: number }) {
  const { data: job, isError, error, refetch, isFetching } = useImportJob(jobId)

  if (!job) {
    return isError ? (
      <div className="alert alert--error" role="alert">
        <Icon name="alert" />
        <span>{errorMessage(error)} <button type="button" className="btn btn--sm" onClick={() => refetch()}>Tentar novamente</button></span>
      </div>
    ) : (
      <p role="status" className="card__hint">Consultando importação…</p>
    )
  }

  return (
    <div className="job" aria-live="polite">
      <div className="job__head">
        <span className="job__name" title={job.filename}>{job.filename}</span>
        <StatusBadge status={job.status} />
      </div>
      <ProgressBar job={job} />
      <div className="counters">
        <Counter label="Linhas lidas" value={job.parsed_lines + job.invalid_lines} />
        <Counter label="Válidas" value={job.parsed_lines} />
        <Counter label="Inválidas" value={job.invalid_lines} />
      </div>
      {isError && (
        <p className="field__error" role="alert">
          Falha ao atualizar o progresso: {errorMessage(error)}. {isFetching ? 'Tentando novamente…' : ''}
        </p>
      )}
      <JobOutcome job={job} />
    </div>
  )
}

function ProgressBar({ job }: { job: ImportJob }) {
  const processed = job.parsed_lines + job.invalid_lines
  const known = job.total_lines != null && job.total_lines > 0
  const ratio = job.status === 'DONE' ? 1 : known ? Math.min(processed / job.total_lines!, 1) : 0
  const running = job.status === 'PENDING' || job.status === 'PROCESSING'
  const modifier = job.status === 'DONE' ? ' progress__bar--done' : job.status === 'FAILED' ? ' progress__bar--failed' : !known ? ' progress__bar--indeterminate' : ''

  return (
    <div>
      <div
        className="progress"
        role="progressbar"
        aria-label="Progresso da importação"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={running && !known ? undefined : Math.round(ratio * 100)}
      >
        <div className={`progress__bar${modifier}`} style={{ width: `${(job.status === 'FAILED' ? 1 : ratio) * 100}%` }} />
      </div>
      {running && known && (
        <p className="card__hint">{formatPercent(ratio)} · {formatNumber(processed)} de {formatNumber(job.total_lines!)} linhas</p>
      )}
    </div>
  )
}

function Counter({ label, value }: { label: string; value: number }) {
  return (
    <div className="counter">
      <div className="counter__label">{label}</div>
      <div className="counter__value">{formatNumber(value)}</div>
    </div>
  )
}

function JobOutcome({ job }: { job: ImportJob }) {
  if (job.status === 'FAILED') {
    return (
      <div className="alert alert--error" role="alert">
        <Icon name="alert" />
        <span>A importação falhou{job.error ? `: ${job.error}` : '.'}</span>
      </div>
    )
  }
  if (job.status !== 'DONE') return null

  const total = job.parsed_lines + job.invalid_lines
  const took = job.finished_at ? Date.parse(job.finished_at) - Date.parse(job.created_at) : NaN
  return (
    <>
      <div className="alert alert--ok" role="status">
        <Icon name="check" />
        <span>
          Importação concluída{Number.isFinite(took) ? ` em ${formatDuration(took)}` : ''}.
          {job.invalid_lines > 0 && ` ${formatPercent(job.invalid_lines / Math.max(total, 1))} das linhas não puderam ser interpretadas.`}
        </span>
      </div>
      <div className="actions">
        <Link className="btn btn--primary" to={`/logs?import_id=${job.id}`}><Icon name="list" /> Ver logs</Link>
        <Link className="btn" to={`/dashboard?import_id=${job.id}`}><Icon name="chart" /> Abrir dashboard</Link>
      </div>
    </>
  )
}

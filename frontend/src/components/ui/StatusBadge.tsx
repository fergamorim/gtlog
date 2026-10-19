import type { ImportStatus } from '../../api/types'
import { Icon } from './Icon'

const LABELS: Record<ImportStatus, string> = {
  PENDING: 'Na fila',
  PROCESSING: 'Processando',
  DONE: 'Concluída',
  FAILED: 'Falhou',
}

export function StatusBadge({ status }: { status: ImportStatus }) {
  const running = status === 'PENDING' || status === 'PROCESSING'
  return (
    <span className={`status-badge status-badge--${status}`}>
      {running && <span className="spinner" aria-hidden="true" />}
      {status === 'DONE' && <Icon name="check" size={12} />}
      {status === 'FAILED' && <Icon name="alert" size={12} />}
      {LABELS[status]}
    </span>
  )
}

import { useImports } from '../../api/queries'
import { formatDateTime } from '../../lib/format'

interface ImportSelectProps {
  value: number | null
  onChange: (id: number | null) => void
}

export function ImportSelect({ value, onChange }: ImportSelectProps) {
  const { data, isPending, isError } = useImports()
  const known = data?.some((job) => job.id === value)

  return (
    <div className="field">
      <label className="field__label" htmlFor="import-select">Importação</label>
      <select
        id="import-select"
        className="select"
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">{isPending ? 'Carregando…' : isError ? 'Todas (erro ao listar)' : 'Todas as importações'}</option>
        {value != null && !known && <option value={value}>Importação #{value}</option>}
        {data?.map((job) => (
          <option key={job.id} value={job.id}>
            #{job.id} · {job.filename} · {formatDateTime(job.created_at)}
          </option>
        ))}
      </select>
    </div>
  )
}

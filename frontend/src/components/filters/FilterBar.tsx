import { useMemo, useState } from 'react'
import { useFacets } from '../../api/queries'
import { countActiveFilters, type FilterKey, type LogFilters } from '../../lib/filters'
import { statusOptions } from '../../lib/status'
import { HttpStatusOption } from '../ui/HttpStatus'
import { Icon } from '../ui/Icon'
import { DateRangeFilter } from './DateRangeFilter'
import { ImportSelect } from './ImportSelect'
import { LevelChips } from './LevelChips'
import { MultiSelect } from './MultiSelect'
import { SearchInput } from './SearchInput'

interface FilterBarProps {
  filters: LogFilters
  onChange: (patch: Partial<LogFilters>) => void
  onClear: () => void
  /** Which filters this view offers (the dashboard hides level and text search). */
  keys: FilterKey[]
}

export function FilterBar({ filters, onChange, onClear, keys }: FilterBarProps) {
  const [open, setOpen] = useState(false)
  const facets = useFacets()
  const has = (key: FilterKey) => keys.includes(key)
  const active = countActiveFilters(filters, keys)
  const statusCodes = facets.data?.status_codes
  const statuses = useMemo(() => statusOptions(statusCodes ?? []), [statusCodes])

  return (
    <section className="card filters" aria-label="Filtros">
      <button type="button" className="btn filters__toggle" aria-expanded={open} aria-controls="filters-panel" onClick={() => setOpen((o) => !o)}>
        <span><Icon name="filter" /> Filtros{active ? ` (${active})` : ''}</span>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} />
      </button>
      <div id="filters-panel" className={`filters__body${open ? ' filters__body--open' : ''}`}>
        {(has('q') || has('level')) && (
          <div className="filters__panel">
            {has('q') && <SearchInput value={filters.q} onChange={(q) => onChange({ q })} />}
            {has('level') && <LevelChips value={filters.level} onChange={(level) => onChange({ level })} />}
          </div>
        )}
        <div className="filters__panel">
          {has('start') && (
            <DateRangeFilter start={filters.start} end={filters.end} onChange={(range) => onChange(range)} />
          )}
          {has('service') && (
            <MultiSelect
              label="Serviço"
              options={facets.data?.services ?? []}
              value={filters.service}
              onChange={(service) => onChange({ service })}
              loading={facets.isPending}
              error={facets.isError}
              onRetry={() => facets.refetch()}
            />
          )}
          {has('category') && (
            <MultiSelect
              label="Categoria"
              options={facets.data?.categories ?? []}
              value={filters.category}
              onChange={(category) => onChange({ category })}
              loading={facets.isPending}
              error={facets.isError}
              onRetry={() => facets.refetch()}
            />
          )}
          {has('status') && (
            <MultiSelect
              label="Código HTTP"
              options={statuses}
              value={filters.status}
              onChange={(status) => onChange({ status })}
              loading={facets.isPending}
              error={facets.isError}
              onRetry={() => facets.refetch()}
              renderOption={renderStatus}
            />
          )}
          {has('importId') && <ImportSelect value={filters.importId} onChange={(importId) => onChange({ importId })} />}
          <div className="filters__actions">
            <button type="button" className="btn btn--ghost" onClick={onClear} disabled={!active}>
              <Icon name="close" /> Limpar filtros{active ? ` (${active})` : ''}
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

const renderStatus = (status: string) => <HttpStatusOption status={status} />

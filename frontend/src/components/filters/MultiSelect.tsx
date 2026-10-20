import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Icon } from '../ui/Icon'

interface MultiSelectProps {
  label: string
  options: string[]
  value: string[]
  onChange: (value: string[]) => void
  loading?: boolean
  error?: boolean
  onRetry?: () => void
}

/** Dropdown with checkboxes; shows a search box when there are many options. */
export function MultiSelect({ label, options, value, onChange, loading, error, onRetry }: MultiSelectProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const popoverId = useId()

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        rootRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Selected values stay listed even if they are not in the facets (e.g. from a shared link).
  const allOptions = useMemo(() => [...new Set([...value, ...options])], [value, options])
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    return term ? allOptions.filter((o) => o.toLowerCase().includes(term)) : allOptions
  }, [allOptions, search])

  const summary = value.length === 0 ? 'Todos' : value.length === 1 ? value[0] : `${value.length} selecionados`
  const toggle = (option: string) =>
    onChange(value.includes(option) ? value.filter((v) => v !== option) : [...value, option])

  return (
    <div className="field multiselect" ref={rootRef}>
      <span className="field__label">{label}</span>
      <button
        type="button"
        className="btn multiselect__button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        aria-label={`${label}: ${summary}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="multiselect__value">{summary}</span>
        <Icon name={open ? 'chevronUp' : 'chevronDown'} />
      </button>
      {open && (
        <div className="multiselect__popover" id={popoverId}>
          {allOptions.length > 8 && (
            <div className="multiselect__search">
              <input
                className="input"
                type="search"
                placeholder={`Filtrar ${label.toLowerCase()}…`}
                aria-label={`Filtrar opções de ${label.toLowerCase()}`}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                autoFocus
              />
            </div>
          )}
          {loading ? (
            <p className="multiselect__empty">Carregando opções…</p>
          ) : error ? (
            <div className="multiselect__empty">
              Erro ao carregar opções.{' '}
              {onRetry && <button type="button" className="btn btn--sm" onClick={onRetry}>Tentar novamente</button>}
            </div>
          ) : visible.length === 0 ? (
            <p className="multiselect__empty">Nenhuma opção.</p>
          ) : (
            <ul className="multiselect__list" aria-label={label}>
              {visible.map((option) => (
                <li key={option}>
                  <label className="multiselect__option">
                    <input type="checkbox" checked={value.includes(option)} onChange={() => toggle(option)} />
                    {option}
                  </label>
                </li>
              ))}
            </ul>
          )}
          <div className="multiselect__footer">
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => onChange([])} disabled={!value.length}>
              Limpar
            </button>
            <button type="button" className="btn btn--sm" onClick={() => setOpen(false)}>Fechar</button>
          </div>
        </div>
      )}
    </div>
  )
}

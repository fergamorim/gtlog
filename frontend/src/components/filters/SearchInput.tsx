import { useEffect, useRef, useState } from 'react'
import { useDebounce } from '../../hooks/useDebounce'
import { Icon } from '../ui/Icon'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  delay?: number
}

/** Text search that commits after the user pauses typing (or immediately on Enter). */
export function SearchInput({ value, onChange, delay = 300 }: SearchInputProps) {
  const [text, setText] = useState(value)
  const debounced = useDebounce(text, delay)
  const latest = useRef({ value, onChange })
  latest.current = { value, onChange }

  // Commit the debounced text (only when it actually changed).
  useEffect(() => {
    if (debounced.trim() !== latest.current.value) latest.current.onChange(debounced.trim())
  }, [debounced])

  // Follow external changes, e.g. "Limpar filtros" or a link with ?q=.
  useEffect(() => {
    setText((current) => (current.trim() === value ? current : value))
  }, [value])

  return (
    <div className="field filters__search">
      <label className="field__label" htmlFor="log-search">Busca</label>
      <div className="search">
        <Icon name="search" />
        <input
          id="log-search"
          className="input"
          type="search"
          placeholder="Buscar na mensagem ou serviço (ex.: pay, timeout)"
          title="Prefixos funcionam (pay encontra payments). Use aspas para buscar uma frase exata."
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && text.trim() !== value) onChange(text.trim())
          }}
          autoComplete="off"
          spellCheck={false}
        />
      </div>
    </div>
  )
}

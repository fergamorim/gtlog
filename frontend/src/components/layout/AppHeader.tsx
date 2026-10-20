import { NavLink, useLocation } from 'react-router-dom'
import { useApiHealth } from '../../api/queries'
import { useTheme } from '../../hooks/useTheme'
import { FILTER_PARAMS } from '../../lib/filters'
import { Icon } from '../ui/Icon'

/** Keeps the filter params when switching between Dashboard and Logs (drops view-only params like `log`). */
function useCarriedSearch(): string {
  const { search, pathname } = useLocation()
  if (pathname !== '/logs' && pathname !== '/dashboard') return ''
  const current = new URLSearchParams(search)
  const carried = new URLSearchParams()
  current.forEach((value, key) => {
    if ((FILTER_PARAMS as readonly string[]).includes(key)) carried.append(key, value)
  })
  const query = carried.toString()
  return query ? `?${query}` : ''
}

function ApiStatus() {
  const { isPending, isError } = useApiHealth()
  const state = isPending ? 'checking' : isError ? 'down' : 'up'
  const label = isPending ? 'Verificando API…' : isError ? 'API indisponível' : 'API online'
  return (
    <span className={`api-status api-status--${state}`} role="status" title={label}>
      <span className="api-status__dot" aria-hidden="true" />
      <span className="api-status__label">{label}</span>
    </span>
  )
}

export function AppHeader() {
  const search = useCarriedSearch()
  const { theme, toggle } = useTheme()

  return (
    <header className="header">
      <NavLink to="/dashboard" className="brand" aria-label="GTLog, início">
        <span className="brand__mark" aria-hidden="true"><Icon name="list" size={15} /></span>
        <span className="brand__name">GTLog</span>
      </NavLink>
      <nav className="nav" aria-label="Principal">
        <NavLink to={{ pathname: '/dashboard', search }}><Icon name="chart" /> Dashboard</NavLink>
        <NavLink to={{ pathname: '/logs', search }}><Icon name="list" /> Logs</NavLink>
        <NavLink to="/importar"><Icon name="upload" /> Importar</NavLink>
      </nav>
      <div className="header__tools">
        <ApiStatus />
        <button
          type="button"
          className="btn btn--ghost btn--icon"
          onClick={toggle}
          aria-label={theme === 'dark' ? 'Usar tema claro' : 'Usar tema escuro'}
          title={theme === 'dark' ? 'Tema claro' : 'Tema escuro'}
        >
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
        </button>
      </div>
    </header>
  )
}

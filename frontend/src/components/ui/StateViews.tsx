import type { ReactNode } from 'react'
import { errorMessage } from '../../api/client'
import { Icon, type IconName } from './Icon'

interface EmptyStateProps {
  title: string
  text?: ReactNode
  icon?: IconName
  children?: ReactNode
}

export function EmptyState({ title, text, icon = 'inbox', children }: EmptyStateProps) {
  return (
    <div className="state" role="status">
      <div className="state__icon"><Icon name={icon} size={22} /></div>
      <p className="state__title">{title}</p>
      {text && <p className="state__text">{text}</p>}
      {children && <div className="state__actions">{children}</div>}
    </div>
  )
}

interface ErrorStateProps {
  error: unknown
  title?: string
  onRetry?: () => void
  retrying?: boolean
}

export function ErrorState({ error, title = 'Não foi possível carregar os dados', onRetry, retrying }: ErrorStateProps) {
  return (
    <div className="state state--error" role="alert">
      <div className="state__icon"><Icon name="alert" size={22} /></div>
      <p className="state__title">{title}</p>
      <p className="state__text">{errorMessage(error)}</p>
      {onRetry && (
        <div className="state__actions">
          <button type="button" className="btn btn--primary" onClick={onRetry} disabled={retrying}>
            {retrying ? <span className="spinner" aria-hidden="true" /> : <Icon name="refresh" />}
            Tentar novamente
          </button>
        </div>
      )}
    </div>
  )
}

import { Link } from 'react-router-dom'
import type { CriticalAlert } from '../../hooks/useCriticalAlerts'
import { Icon } from '../ui/Icon'

interface CriticalAlertsProps {
  alerts: CriticalAlert[]
  onDismiss: (watchId: number) => void
}

/** In-page copy of the latest CRITICAL alerts, shown even when the system hides the notification. */
export function CriticalAlerts({ alerts, onDismiss }: CriticalAlertsProps) {
  return (
    <div className="critical-alerts" role="region" aria-label="Alertas de erros críticos" aria-live="assertive">
      {alerts.map((alert) => (
        <div key={alert.watchId} className="critical-alert">
          <Icon name="bell" />
          <div className="critical-alert__text">
            <strong>{alert.title}</strong>
            {alert.message && <span className="critical-alert__message">{alert.message}</span>}
            <Link to={alert.url} onClick={() => onDismiss(alert.watchId)}>Ver logs críticos</Link>
          </div>
          <button type="button" className="btn btn--sm btn--ghost btn--icon" onClick={() => onDismiss(alert.watchId)} aria-label="Fechar alerta">
            <Icon name="close" />
          </button>
        </div>
      ))}
    </div>
  )
}

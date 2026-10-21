import { useEffect, useRef, useSyncExternalStore } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWatches } from '../api/queries'
import type { LogWatch } from '../api/types'
import { alertPermission, alertsEnabled, alertsOptedIn, enableAlerts, setAlertsOptedIn, subscribeAlerts } from '../lib/alerts'
import { formatNumber } from '../lib/format'

/** The opt-in state for the alerts toggle; re-renders when it changes in any component. */
export function useAlertSettings() {
  const optedIn = useSyncExternalStore(subscribeAlerts, alertsOptedIn)
  const permission = alertPermission()
  return {
    permission,
    enabled: optedIn && permission === 'granted',
    enable: enableAlerts,
    disable: () => setAlertsOptedIn(false),
  }
}

export const criticalLogsUrl = (watch: LogWatch) => `/logs?import_id=${watch.import_id}&level=CRITICAL`

/**
 * Shows a browser notification when a watch reads new CRITICAL lines, while any GTLog tab is open.
 * Counts first seen are the baseline, so reloading the page does not repeat old alerts.
 */
export function useCriticalAlerts() {
  const { enabled } = useAlertSettings()
  // Keep polling in a background tab, which is where alerts matter most.
  const { data } = useWatches({ inBackground: enabled })
  const navigate = useNavigate()
  const previous = useRef(new Map<number, number>())

  useEffect(() => {
    if (!data) return
    const grown = data.filter((watch) => {
      const before = previous.current.get(watch.id)
      return before !== undefined && watch.critical_lines > before
    })
    const counts = new Map(data.map((watch) => [watch.id, watch.critical_lines]))
    if (alertsEnabled()) {
      for (const watch of grown) {
        const added = watch.critical_lines - (previous.current.get(watch.id) ?? 0)
        const title = added === 1 ? `Erro crítico em ${watch.path}` : `${formatNumber(added)} erros críticos em ${watch.path}`
        try {
          // The tag replaces an unread alert of the same watch instead of piling them up.
          const notification = new Notification(title, {
            body: watch.last_critical_message ?? undefined,
            tag: `gtlog-watch-${watch.id}`,
          })
          notification.onclick = () => {
            window.focus()
            navigate(criticalLogsUrl(watch))
            notification.close()
          }
        } catch {
          // Some browsers (Android Chrome) only notify through a service worker; the count still shows on the page.
        }
      }
    }
    previous.current = counts
  }, [data, navigate])
}

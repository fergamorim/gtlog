import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWatches } from '../api/queries'
import type { LogWatch } from '../api/types'
import {
  alertPermission,
  alertsEnabled,
  alertsOptedIn,
  enableAlerts,
  setAlertsOptedIn,
  showNotification,
  subscribeAlerts,
} from '../lib/alerts'
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

export interface CriticalAlert {
  watchId: number
  title: string
  message: string | null
  url: string
}

const MAX_ALERTS = 3

/**
 * Alerts when a watch reads new CRITICAL lines, while any GTLog tab is open: a system notification, an
 * in-page alert (for when the system hides the notification) and the unread count in the tab title.
 * Counts first seen once a watch caught up are the baseline, so reloading the page or creating a watch on a
 * file that already has CRITICAL lines does not announce old ones.
 */
export function useCriticalAlerts() {
  const { enabled } = useAlertSettings()
  // Keep polling in a background tab, which is where alerts matter most.
  const { data } = useWatches({ inBackground: enabled })
  const navigate = useNavigate()
  const previous = useRef(new Map<number, number>())
  const [alerts, setAlerts] = useState<CriticalAlert[]>([])
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    if (!data) return
    const grown = data.filter((watch) => {
      const before = previous.current.get(watch.id)
      return before !== undefined && watch.critical_lines > before
    })
    if (grown.length && alertsEnabled()) {
      const fresh = grown.map((watch) => {
        const added = watch.critical_lines - (previous.current.get(watch.id) ?? 0)
        const title = added === 1 ? `Erro crítico em ${watch.path}` : `${formatNumber(added)} erros críticos em ${watch.path}`
        const alert = { watchId: watch.id, title, message: watch.last_critical_message, url: criticalLogsUrl(watch) }
        // The tag replaces an unread alert of the same watch instead of piling them up.
        showNotification(title, { body: alert.message ?? undefined, tag: `gtlog-watch-${watch.id}` }, () => navigate(alert.url))
        return alert
      })
      const ids = new Set(fresh.map((alert) => alert.watchId))
      setAlerts((current) => [...fresh, ...current.filter((alert) => !ids.has(alert.watchId))].slice(0, MAX_ALERTS))
      if (document.hidden) setUnread((count) => count + fresh.length)
    }
    // A watch's baseline is taken once it has caught up with its file, so the CRITICAL lines the file
    // already had (imported by the first polls after it is created) are not announced as new.
    previous.current = new Map(
      data
        .filter((watch) => previous.current.has(watch.id) || caughtUp(watch))
        .map((watch) => [watch.id, watch.critical_lines]),
    )
  }, [data, navigate])

  const clearUnread = useCallback(() => setUnread(0), [])
  useUnreadTitle(unread, clearUnread)

  const dismiss = useCallback((watchId: number) => setAlerts((current) => current.filter((alert) => alert.watchId !== watchId)), [])
  return { alerts, dismiss }
}

/**
 * Read up to the end of its file: polled at least once, and not rescheduled right away (the API sets
 * next_check_at to the poll time itself while a backlog is still being drained).
 */
export function caughtUp(watch: LogWatch): boolean {
  return watch.last_checked_at != null && new Date(watch.next_check_at) > new Date(watch.last_checked_at)
}

/** "(2) GTLog" in the tab title while alerts arrived in a hidden tab; cleared when the tab is shown. */
function useUnreadTitle(unread: number, clear: () => void) {
  const base = useRef(document.title.replace(/^\(\d+\) /, ''))
  useEffect(() => {
    document.title = unread ? `(${unread}) ${base.current}` : base.current
  }, [unread])
  useEffect(() => {
    const onVisible = () => {
      if (!document.hidden) clear()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [clear])
}

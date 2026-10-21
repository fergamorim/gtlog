/** Browser notifications for CRITICAL lines read by watches: the user's opt-in, kept in localStorage. */

const STORAGE_KEY = 'gtlog-critical-alerts'
const listeners = new Set<() => void>()

/** False without the Notification API, e.g. on plain http outside localhost. */
export function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window
}

export function alertPermission(): NotificationPermission | 'unsupported' {
  return notificationsSupported() ? Notification.permission : 'unsupported'
}

export function alertsOptedIn(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'on'
  } catch {
    return false
  }
}

/** Opted in and allowed by the browser: notifications will show. */
export function alertsEnabled(): boolean {
  return alertsOptedIn() && alertPermission() === 'granted'
}

export function setAlertsOptedIn(on: boolean): void {
  try {
    if (on) localStorage.setItem(STORAGE_KEY, 'on')
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage may be unavailable (private mode); the choice just won't persist.
  }
  listeners.forEach((listener) => listener())
}

/** Asks the browser for permission (it shows its own prompt) and opts in when granted. */
export async function enableAlerts(): Promise<NotificationPermission | 'unsupported'> {
  if (!notificationsSupported()) return 'unsupported'
  const permission = Notification.permission === 'default' ? await Notification.requestPermission() : Notification.permission
  setAlertsOptedIn(permission === 'granted')
  return permission
}

export function subscribeAlerts(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

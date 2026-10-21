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

/** Older Safari answers through a callback instead of the returned promise. */
function askPermission(): Promise<NotificationPermission> {
  return new Promise((resolve) => {
    const answer = Notification.requestPermission(resolve)
    if (answer) answer.then(resolve, () => resolve(Notification.permission))
  })
}

/** Asks the browser for permission (it shows its own prompt) and opts in when granted. */
export async function enableAlerts(): Promise<NotificationPermission | 'unsupported'> {
  if (!notificationsSupported()) return 'unsupported'
  const permission = Notification.permission === 'default' ? await askPermission() : Notification.permission
  setAlertsOptedIn(permission === 'granted')
  return permission
}

/**
 * Shows a system notification; false when the browser refused to build one (some only notify through a
 * service worker). The operating system can still hide it (Focus, or notifications off for the browser).
 */
export function showNotification(title: string, options: NotificationOptions, onClick?: () => void): boolean {
  try {
    const notification = new Notification(title, options)
    notification.onclick = () => {
      window.focus()
      onClick?.()
      notification.close()
    }
    return true
  } catch {
    return false
  }
}

export function subscribeAlerts(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

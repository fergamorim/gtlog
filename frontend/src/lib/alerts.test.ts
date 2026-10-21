import { afterEach, describe, expect, it, vi } from 'vitest'
import { alertsEnabled, enableAlerts } from './alerts'

afterEach(() => localStorage.clear())

describe('enableAlerts', () => {
  it('understands the callback answer of older Safari', async () => {
    const legacy = {
      permission: 'default' as NotificationPermission,
      requestPermission: vi.fn((callback: (permission: NotificationPermission) => void) => {
        legacy.permission = 'granted'
        callback('granted')
        return undefined
      }),
    }
    vi.stubGlobal('Notification', legacy)

    await expect(enableAlerts()).resolves.toBe('granted')
    expect(alertsEnabled()).toBe(true)
  })

  it('does not opt in when the permission is refused, or without the Notification API', async () => {
    vi.stubGlobal('Notification', { permission: 'default', requestPermission: async () => 'denied' })
    await expect(enableAlerts()).resolves.toBe('denied')
    expect(alertsEnabled()).toBe(false)

    vi.unstubAllGlobals()
    await expect(enableAlerts()).resolves.toBe('unsupported')
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { queryKeys } from '../api/queries'
import type { LogWatch } from '../api/types'
import { WatchAlerts } from '../components/imports/WatchAlerts'
import { CriticalAlerts } from '../components/layout/CriticalAlerts'
import { setAlertsOptedIn } from '../lib/alerts'
import { json, mockFetch, renderWithProviders } from '../test/utils'
import { useCriticalAlerts } from './useCriticalAlerts'

const watch = (critical: number, message: string | null = null, overrides: Partial<LogWatch> = {}): LogWatch => ({
  id: 4, path: 'live.log', interval_seconds: 5, active: true, import_id: 9, format: 'text', offset: 0,
  parsed_lines: 10, invalid_lines: 0, last_error: null, critical_lines: critical, last_critical_message: message,
  last_critical_at: null, created_at: '2026-10-05T17:00:00Z', last_checked_at: '2026-10-05T17:00:00Z',
  next_check_at: '2026-10-05T17:00:05Z', ...overrides,
})

/** A fake Notification class that records what was shown. */
function stubNotifications(permission: NotificationPermission, answer: NotificationPermission = permission) {
  const shown: { title: string; options?: NotificationOptions; instance: { onclick: null | (() => void); close: () => void } }[] = []
  class FakeNotification {
    static permission = permission
    static requestPermission = vi.fn(async () => {
      FakeNotification.permission = answer
      return answer
    })
    onclick: null | (() => void) = null
    close = vi.fn()
    constructor(title: string, options?: NotificationOptions) {
      shown.push({ title, options, instance: this })
    }
  }
  vi.stubGlobal('Notification', FakeNotification)
  return { shown, FakeNotification }
}

beforeEach(() => localStorage.clear())
afterEach(() => localStorage.clear())

describe('useCriticalAlerts', () => {
  function setup(initial: LogWatch) {
    let current = initial
    mockFetch(() => json([current]))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    let location = ''
    function Probe() {
      location = useLocation().pathname + useLocation().search
      return null
    }
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>
        <MemoryRouter>{children}<Probe /></MemoryRouter>
      </QueryClientProvider>
    )
    const hook = renderHook(() => useCriticalAlerts(), { wrapper })
    return {
      hook,
      client,
      location: () => location,
      next: async (value: LogWatch) => {
        current = value
        await client.refetchQueries({ queryKey: queryKeys.watches })
      },
    }
  }

  it('notifies once per poll when the CRITICAL count grows, and a click opens those logs', async () => {
    const { shown } = stubNotifications('granted')
    setAlertsOptedIn(true)
    const { client, next, location, hook } = setup(watch(3, 'old'))
    await waitFor(() => expect(client.getQueryData<LogWatch[]>(queryKeys.watches)?.[0].critical_lines).toBe(3))
    // Counts already there when the page loads are the baseline.
    expect(shown).toHaveLength(0)

    await next(watch(5, 'disk full on /var/lib/db'))
    await waitFor(() => expect(shown).toHaveLength(1))
    expect(shown[0].title).toBe('2 erros críticos em live.log')
    expect(shown[0].options).toEqual({ body: 'disk full on /var/lib/db', tag: 'gtlog-watch-4' })

    // The same alert shows in the page, for when the system hides the notification.
    expect(hook.result.current.alerts).toEqual([
      { watchId: 4, title: '2 erros críticos em live.log', message: 'disk full on /var/lib/db', url: '/logs?import_id=9&level=CRITICAL' },
    ])

    await next(watch(5, 'disk full on /var/lib/db'))
    await next(watch(6, 'again'))
    await waitFor(() => expect(shown).toHaveLength(2))
    expect(shown[1].title).toBe('Erro crítico em live.log')

    vi.spyOn(window, 'focus').mockImplementation(() => {})
    shown[1].instance.onclick?.()
    await waitFor(() => expect(location()).toBe('/logs?import_id=9&level=CRITICAL'))
    expect(shown[1].instance.close).toHaveBeenCalled()
    // One in-page alert per watch, the newest replacing the older one.
    expect(hook.result.current.alerts.map((alert) => alert.title)).toEqual(['Erro crítico em live.log'])
    act(() => hook.result.current.dismiss(4))
    expect(hook.result.current.alerts).toEqual([])
  })

  it('does not announce the CRITICAL lines a file already had when its watch is created', async () => {
    const { shown } = stubNotifications('granted')
    setAlertsOptedIn(true)
    // Just created: never read (what the create response puts in the cache).
    const { client, next } = setup(watch(0, null, { last_checked_at: null }))
    await waitFor(() => expect(client.getQueryData<LogWatch[]>(queryKeys.watches)).toHaveLength(1))

    // First poll, more than one poll's worth: due again right away, still catching up.
    // act flushes each render, so the hook sees every poll and not just the last one.
    await act(() => next(watch(300, 'old', { next_check_at: '2026-10-05T17:00:00Z' })))
    // Caught up with the file: the existing 500 lines become the baseline.
    await act(() => next(watch(500, 'old')))
    expect(shown).toHaveLength(0)

    await next(watch(501, 'new one'))
    await waitFor(() => expect(shown).toHaveLength(1))
    expect(shown[0].title).toBe('Erro crítico em live.log')
  })

  it('counts alerts of a hidden tab in the title until the tab is shown again', async () => {
    stubNotifications('granted')
    setAlertsOptedIn(true)
    document.title = 'GTLog'
    let hidden = true
    vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden)
    const { client, next } = setup(watch(0))
    await waitFor(() => expect(client.getQueryData(queryKeys.watches)).toBeDefined())

    await next(watch(1, 'boom'))
    await waitFor(() => expect(document.title).toBe('(1) GTLog'))
    await next(watch(3, 'boom'))
    await waitFor(() => expect(document.title).toBe('(2) GTLog'))

    hidden = false
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await waitFor(() => expect(document.title).toBe('GTLog'))
  })

  it('still alerts in the page when the browser refuses to build a notification', async () => {
    vi.stubGlobal('Notification', Object.assign(function Refused() {
      throw new TypeError('Illegal constructor')
    }, { permission: 'granted' }))
    setAlertsOptedIn(true)
    const { client, next, hook } = setup(watch(0))
    await waitFor(() => expect(client.getQueryData(queryKeys.watches)).toBeDefined())
    await next(watch(1, 'boom'))
    await waitFor(() => expect(hook.result.current.alerts).toHaveLength(1))
  })

  it('stays silent when alerts are off or the browser did not allow them', async () => {
    const { shown } = stubNotifications('default')
    setAlertsOptedIn(true)
    const { client, next } = setup(watch(0))
    await waitFor(() => expect(client.getQueryData(queryKeys.watches)).toBeDefined())
    await next(watch(2, 'boom'))

    setAlertsOptedIn(false)
    ;(Notification as unknown as { permission: string }).permission = 'granted'
    await next(watch(4, 'boom'))
    expect(shown).toHaveLength(0)
  })
})

describe('WatchAlerts', () => {
  it('asks for permission and then shows the alerts as active', async () => {
    const { FakeNotification, shown } = stubNotifications('default', 'granted')
    renderWithProviders(<WatchAlerts />)
    await userEvent.click(screen.getByRole('button', { name: 'Ativar alertas' }))

    expect(FakeNotification.requestPermission).toHaveBeenCalled()
    expect(await screen.findByText(/Alertas ativos/)).toBeInTheDocument()
    expect(localStorage.getItem('gtlog-critical-alerts')).toBe('on')

    await userEvent.click(screen.getByRole('button', { name: 'Testar' }))
    expect(shown.map((n) => n.title)).toEqual(['GTLog: teste de alerta'])
    expect(screen.getByRole('status')).toHaveTextContent(/Ajustes do Sistema › Notificações/)

    await userEvent.click(screen.getByRole('button', { name: 'Desativar alertas' }))
    expect(screen.getByRole('button', { name: 'Ativar alertas' })).toBeInTheDocument()
    expect(localStorage.getItem('gtlog-critical-alerts')).toBeNull()
  })

  it('explains a refused permission and a browser without notifications', async () => {
    stubNotifications('default', 'denied')
    const { unmount } = renderWithProviders(<WatchAlerts />)
    await userEvent.click(screen.getByRole('button', { name: 'Ativar alertas' }))
    expect(await screen.findByText(/Notificações bloqueadas para este site/)).toBeInTheDocument()
    unmount()

    vi.unstubAllGlobals()
    renderWithProviders(<WatchAlerts />)
    expect(screen.getByText(/Alertas indisponíveis/)).toBeInTheDocument()
  })
})

describe('CriticalAlerts', () => {
  it('links to the CRITICAL logs and closes', async () => {
    const onDismiss = vi.fn()
    renderWithProviders(
      <CriticalAlerts
        alerts={[{ watchId: 4, title: 'Erro crítico em live.log', message: 'disk full', url: '/logs?import_id=9&level=CRITICAL' }]}
        onDismiss={onDismiss}
      />,
    )
    const region = screen.getByRole('region', { name: 'Alertas de erros críticos' })
    expect(region).toHaveTextContent('Erro crítico em live.logdisk full')
    expect(screen.getByRole('link', { name: 'Ver logs críticos' })).toHaveAttribute('href', '/logs?import_id=9&level=CRITICAL')
    await userEvent.click(screen.getByRole('button', { name: 'Fechar alerta' }))
    expect(onDismiss).toHaveBeenCalledWith(4)
  })
})

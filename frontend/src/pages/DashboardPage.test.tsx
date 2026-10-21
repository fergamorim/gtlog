import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EMPTY_STATS, json, mockFetch, renderWithProviders } from '../test/utils'
import { DashboardPage } from './DashboardPage'

describe('DashboardPage', () => {
  it('applies the HTTP status filter to /stats and offers it in the filter bar', async () => {
    const fetch = mockFetch((url) => {
      switch (url.pathname) {
        case '/logs/facets':
          return json({ services: [], categories: [], status_codes: [404] })
        case '/imports':
          return json([])
        case '/stats':
          return json(EMPTY_STATS)
        default:
          return json({ detail: 'não encontrado' }, 404)
      }
    })
    renderWithProviders(<DashboardPage />, { route: '/dashboard?status=5xx&status=404&level=ERROR' })

    expect(await screen.findByRole('button', { name: 'Código HTTP: 2 selecionados' })).toBeInTheDocument()
    await waitFor(() => {
      const stats = fetch.mock.calls.map(([input]) => new URL(String(input))).find((u) => u.pathname === '/stats')
      expect(stats?.searchParams.getAll('status')).toEqual(['5xx', '404'])
      expect(stats?.searchParams.has('level')).toBe(false)
    })
  })

  it('shows one chosen day by hour, defaulting to the last day with logs', async () => {
    // Recharts' ResponsiveContainer measures its parent; jsdom has no ResizeObserver.
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })
    const stats = {
      ...EMPTY_STATS, total: 30, bucket: 'day',
      by_level: { DEBUG: 0, INFO: 30, WARNING: 0, ERROR: 0, CRITICAL: 0 },
      first_timestamp: '2026-10-03T08:00:00Z', last_timestamp: '2026-10-05T21:15:00Z',
      timeseries: ['03', '04', '05'].map((d) => ({ bucket: `2026-10-${d}T00:00:00Z`, DEBUG: 0, INFO: 10, WARNING: 0, ERROR: 0, CRITICAL: 0 })),
    }
    const hourly = {
      ...stats, total: 10, bucket: 'hour',
      timeseries: Array.from({ length: 24 }, (_, h) => ({
        bucket: `2026-10-05T${String(h).padStart(2, '0')}:00:00Z`, DEBUG: 0, INFO: h === 21 ? 10 : 0, WARNING: 0, ERROR: 0, CRITICAL: 0,
      })),
    }
    const fetch = mockFetch((url) => {
      if (url.pathname === '/stats') return json(url.searchParams.get('bucket') === 'hour' ? hourly : stats)
      if (url.pathname === '/logs/facets') return json({ services: [], categories: [], status_codes: [] })
      return json([])
    })
    renderWithProviders(<DashboardPage />, { route: '/dashboard?service=auth' })

    const panel = await screen.findByRole('region', { name: 'Volume por hora em um dia' })
    const day = within(panel).getByLabelText('Dia')
    expect(day).toHaveValue('2026-10-05')
    expect(day).toHaveAttribute('min', '2026-10-03')
    expect(within(panel).getByRole('button', { name: 'Próximo dia' })).toBeDisabled()
    expect(await within(panel).findByText('10 logs em 05/10/2026')).toBeInTheDocument()

    const hourlyCalls = () =>
      fetch.mock.calls.map(([input]) => new URL(String(input))).filter((u) => u.searchParams.get('bucket') === 'hour')
    expect(hourlyCalls()[0].searchParams.get('start')).toBe('2026-10-05T00:00:00.000Z')
    expect(hourlyCalls()[0].searchParams.get('end')).toBe('2026-10-06T00:00:00.000Z')
    expect(hourlyCalls()[0].searchParams.get('service')).toBe('auth')

    await userEvent.click(within(panel).getByRole('button', { name: 'Dia anterior' }))
    expect(day).toHaveValue('2026-10-04')
    await waitFor(() => expect(hourlyCalls().slice(-1)[0]?.searchParams.get('start')).toBe('2026-10-04T00:00:00.000Z'))
  })
})

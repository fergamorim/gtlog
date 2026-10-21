import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
})

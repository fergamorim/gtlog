import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { LogEntry } from '../api/types'
import { json, mockFetch, renderWithProviders } from '../test/utils'
import { LogsPage } from './LogsPage'

const ENTRY: LogEntry = {
  id: 1,
  import_id: 1,
  timestamp: '2026-10-05T17:46:57Z',
  level: 'ERROR',
  service: 'payments',
  category: 'timeout',
  status_code: 503,
  message: 'timeout calling auth after 1234ms',
  raw: '2026-10-05T17:46:57Z ERROR [payments] timeout calling auth after 1234ms',
}

/** Default API: facets, imports and stats succeed; /logs is customizable. */
function api(logs: (url: URL) => Response) {
  return mockFetch((url) => {
    switch (url.pathname) {
      case '/logs/facets':
        return json({ services: ['auth', 'payments'], categories: ['timeout'], status_codes: [200, 404, 503] })
      case '/imports':
        return json([])
      case '/logs/count':
        return json({ total: 1 })
      case '/logs':
        return logs(url)
      default:
        return json({ detail: 'não encontrado' }, 404)
    }
  })
}

describe('LogsPage', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows the empty state and clears filters from it', async () => {
    const fetch = api(() => json({ items: [], next_cursor: null }))
    renderWithProviders(<LogsPage />, { route: '/logs?level=ERROR' })

    expect(await screen.findByText('Nenhum log encontrado')).toBeInTheDocument()

    const firstCall = fetch.mock.calls.map(([input]) => new URL(String(input))).find((u) => u.pathname === '/logs')
    expect(firstCall?.searchParams.getAll('level')).toEqual(['ERROR'])

    const state = screen.getByText('Nenhum log encontrado').closest('.state') as HTMLElement
    await userEvent.click(within(state).getByRole('button', { name: 'Limpar filtros' }))

    await waitFor(() => {
      const calls = fetch.mock.calls.map(([input]) => new URL(String(input))).filter((u) => u.pathname === '/logs')
      const last = calls[calls.length - 1]
      expect(last?.searchParams.has('level')).toBe(false)
    })
    // Without filters the empty state points to the import page instead.
    expect(await screen.findByRole('link', { name: 'Importar arquivo' })).toHaveAttribute('href', '/importar')
  })

  it('shows the API error and retries', async () => {
    let fail = true
    api(() => (fail ? json({ detail: 'Banco de dados indisponível.' }, 500) : json({ items: [ENTRY], next_cursor: null })))
    renderWithProviders(<LogsPage />, { route: '/logs' })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Não foi possível carregar os logs')
    expect(alert).toHaveTextContent('Banco de dados indisponível.')

    fail = false
    await userEvent.click(within(alert).getByRole('button', { name: /Tentar novamente/ }))

    expect(await screen.findByText(/Fim dos resultados/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Registros de log' })).toBeInTheDocument()
  })

  it('shows the total from /logs/count with the same filters', async () => {
    const fetch = api(() => json({ items: [ENTRY], next_cursor: null }))
    renderWithProviders(<LogsPage />, { route: '/logs?level=ERROR&q=pay' })

    const summary = await screen.findByText((_, el) => el?.tagName === 'SPAN' && el.textContent === '1 registro')
    expect(summary).toBeInTheDocument()
    const countCall = fetch.mock.calls.map(([input]) => new URL(String(input))).find((u) => u.pathname === '/logs/count')
    expect(countCall?.searchParams.getAll('level')).toEqual(['ERROR'])
    expect(countCall?.searchParams.get('q')).toBe('pay')
    expect(countCall?.searchParams.has('limit')).toBe(false)
  })

  it('closes the drawer and applies the filter in one URL update', async () => {
    const fetch = api(() => json({ items: [ENTRY], next_cursor: null }))
    renderWithProviders(<LogsPage />, { route: '/logs?log=1' })

    const dialog = await screen.findByRole('dialog')
    await userEvent.click(await within(dialog).findByRole('button', { name: /Só nível ERROR/ }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const calls = fetch.mock.calls.map(([input]) => new URL(String(input))).filter((u) => u.pathname === '/logs')
    expect(calls[calls.length - 1].searchParams.getAll('level')).toEqual(['ERROR'])
  })

  it('offers HTTP status classes and codes from the facets and sends `status` to the API', async () => {
    const fetch = api(() => json({ items: [ENTRY], next_cursor: null }))
    renderWithProviders(<LogsPage />, { route: '/logs' })

    await userEvent.click(await screen.findByRole('button', { name: 'Código HTTP: Todos' }))
    const list = await screen.findByRole('list', { name: 'Código HTTP' })
    const labels = within(list).getAllByRole('listitem').map((item) => item.textContent)
    expect(labels).toEqual(['2xx·INFO', '3xx·INFO', '4xx·WARNING', '5xx·ERRORCRITICAL', '200·INFO', '404·WARNING', '503·CRITICAL'])

    await userEvent.click(within(list).getByRole('checkbox', { name: /404/ }))
    await userEvent.click(within(list).getByRole('checkbox', { name: /5xx/ }))

    await waitFor(() => {
      const calls = fetch.mock.calls.map(([input]) => new URL(String(input)))
      const logs = calls.filter((u) => u.pathname === '/logs')
      const counts = calls.filter((u) => u.pathname === '/logs/count')
      expect(logs[logs.length - 1].searchParams.getAll('status')).toEqual(['404', '5xx'])
      expect(counts[counts.length - 1].searchParams.getAll('status')).toEqual(['404', '5xx'])
    })
    expect(screen.getByRole('button', { name: 'Código HTTP: 2 selecionados' })).toBeInTheDocument()
  })

  it('shows the HTTP code in the table and filters by it from the drawer', async () => {
    // jsdom has no layout: give the scroll container a size so the virtualizer renders rows.
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 1200, 600))
    const fetch = api(() => json({ items: [ENTRY, { ...ENTRY, id: 2, status_code: null }], next_cursor: null }))
    renderWithProviders(<LogsPage />, { route: '/logs' })

    const table = await screen.findByRole('table', { name: 'Registros de log' })
    expect(within(table).getByRole('columnheader', { name: 'Código' })).toBeInTheDocument()
    const [first, second] = within(table).getAllByRole('row').slice(1)
    expect(within(first).getAllByRole('cell')[2]).toHaveTextContent('503')
    expect(within(first).getByTitle('HTTP 503 · CRITICAL')).toBeInTheDocument()
    expect(within(second).getAllByRole('cell')[2]).toHaveTextContent('—')

    await userEvent.click(first)
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: /Só o código 503/ }))
    await waitFor(() => {
      const calls = fetch.mock.calls.map(([input]) => new URL(String(input))).filter((u) => u.pathname === '/logs')
      expect(calls[calls.length - 1].searchParams.getAll('status')).toEqual(['503'])
    })
  })

  it('reports a network failure in Portuguese', async () => {
    mockFetch(() => {
      throw new TypeError('Failed to fetch')
    })
    renderWithProviders(<LogsPage />, { route: '/logs' })
    expect(await screen.findByText(/Não foi possível conectar à API/)).toBeInTheDocument()
  })
})

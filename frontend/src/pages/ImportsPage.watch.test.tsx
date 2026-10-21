import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Folder, LogWatch } from '../api/types'
import { json, mockFetch, renderWithProviders } from '../test/utils'
import { ImportsPage } from './ImportsPage'

const SETTINGS = { root: '/watch', host_root: null as string | null, min_interval_seconds: 1, max_interval_seconds: 86_400 }

const watch = (overrides: Partial<LogWatch> = {}): LogWatch => ({
  id: 1, path: 'live.log', interval_seconds: 30, active: true, import_id: 7, format: 'text', offset: 120,
  parsed_lines: 12, invalid_lines: 1, last_error: null, created_at: '2026-10-05T17:00:00Z',
  last_checked_at: '2026-10-05T17:00:30Z', next_check_at: '2026-10-05T17:01:00Z', ...overrides,
})

const FOLDERS: Record<string, Folder> = {
  '': {
    path: '', parent: null,
    entries: [
      { name: 'kaggle', path: 'kaggle', is_dir: true, size: null, modified_at: '2026-10-05T17:00:00Z' },
      { name: 'app.log', path: 'app.log', is_dir: false, size: 2048, modified_at: '2026-10-05T17:00:00Z' },
    ],
  },
  kaggle: {
    path: 'kaggle', parent: '',
    entries: [{ name: 'data.log', path: 'kaggle/data.log', is_dir: false, size: 10, modified_at: '2026-10-05T17:00:00Z' }],
  },
}

function watchApi(watches: LogWatch[], onWrite?: (url: URL, init: RequestInit) => Response, settings = SETTINGS) {
  return mockFetch((url, init) => {
    if (init?.method && init.method !== 'GET' && onWrite) return onWrite(url, init)
    if (url.pathname === '/watches/settings') return json(settings)
    if (url.pathname === '/watches/files') return json(FOLDERS[url.searchParams.get('path') ?? ''])
    if (url.pathname === '/watches') return json(watches)
    if (url.pathname === '/imports') return json([])
    return json({ detail: 'não encontrado' }, 404)
  })
}

const panel = () => screen.getByRole('region', { name: 'Observar arquivo em tempo real' })

describe('ImportsPage live watch', () => {
  it('sends the path and the interval converted to seconds', async () => {
    const fetch = watchApi([], () => json(watch({ interval_seconds: 120 }), 201))
    renderWithProviders(<ImportsPage />)

    await userEvent.type(within(panel()).getByLabelText('Arquivo'), ' live.log ')
    await userEvent.clear(within(panel()).getByLabelText('Intervalo'))
    await userEvent.type(within(panel()).getByLabelText('Intervalo'), '2')
    await userEvent.selectOptions(within(panel()).getByLabelText('Unidade do intervalo'), 'minutos')
    await userEvent.click(within(panel()).getByRole('checkbox'))
    await userEvent.click(within(panel()).getByRole('button', { name: /Observar arquivo/ }))

    const post = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(post?.[0]).toBe('http://localhost:8000/watches')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ path: 'live.log', interval_seconds: 120, start_at_end: true })
    const list = await within(panel()).findByRole('list', { name: 'Arquivos observados' })
    expect(within(list).getByText('a cada 2 min')).toBeInTheDocument()
    expect(within(panel()).getByLabelText('Arquivo')).toHaveValue('')
  })

  it('picks a file by browsing the watch folder and fills in the full host path', async () => {
    const fetch = watchApi([], () => json(watch(), 201), { ...SETTINGS, host_root: '/Users/ana/logs' })
    renderWithProviders(<ImportsPage />)

    expect(await within(panel()).findByText('/Users/ana/logs')).toBeInTheDocument()
    await userEvent.click(within(panel()).getByRole('button', { name: /Selecionar arquivo/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Selecionar arquivo' })
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Abrir pasta kaggle' }))
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Selecionar data.log' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(within(panel()).getByLabelText('Arquivo')).toHaveValue('/Users/ana/logs/kaggle/data.log')
    await userEvent.click(within(panel()).getByRole('button', { name: /Observar arquivo/ }))
    const post = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body)).path).toBe('/Users/ana/logs/kaggle/data.log')
  })

  it('rejects an interval out of range without calling the API', async () => {
    const fetch = watchApi([])
    renderWithProviders(<ImportsPage />)

    await userEvent.type(within(panel()).getByLabelText('Arquivo'), 'live.log')
    await userEvent.clear(within(panel()).getByLabelText('Intervalo'))
    await userEvent.type(within(panel()).getByLabelText('Intervalo'), '0')
    await userEvent.click(within(panel()).getByRole('button', { name: /Observar arquivo/ }))

    expect(await within(panel()).findByRole('alert')).toHaveTextContent('O intervalo deve ser um número inteiro')
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('shows the API detail when the file is refused', async () => {
    const detail = 'O arquivo precisa estar dentro da pasta observável (/watch).'
    watchApi([], () => json({ detail }, 422))
    renderWithProviders(<ImportsPage />)

    await userEvent.type(within(panel()).getByLabelText('Arquivo'), '../etc/passwd')
    await userEvent.click(within(panel()).getByRole('button', { name: /Observar arquivo/ }))

    expect(await within(panel()).findByRole('alert')).toHaveTextContent(detail)
  })

  it('lists watches with their state and pauses one', async () => {
    const fetch = watchApi([watch(), watch({ id: 2, path: 'gone.log', last_error: 'Arquivo não encontrado: gone.log.' })], (url) =>
      json(watch({ active: false }), url.pathname === '/watches/1' ? 200 : 404),
    )
    renderWithProviders(<ImportsPage />)

    const list = await within(panel()).findByRole('list', { name: 'Arquivos observados' })
    const [live, gone] = within(list).getAllByRole('listitem')
    expect(within(live).getByText('Observando')).toBeInTheDocument()
    expect(within(live).getByText('12 válidas')).toBeInTheDocument()
    expect(within(live).getByRole('link', { name: 'Ver logs' })).toHaveAttribute('href', '/logs?import_id=7')
    expect(within(gone).getByText('Com erro')).toBeInTheDocument()
    expect(within(gone).getByText('Arquivo não encontrado: gone.log.')).toBeInTheDocument()

    await userEvent.click(within(live).getByRole('button', { name: 'Pausar' }))

    const patch = fetch.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(patch?.[0]).toBe('http://localhost:8000/watches/1')
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ active: false })
    expect(await within(live).findByText('Pausada')).toBeInTheDocument()
    expect(within(live).getByRole('button', { name: 'Retomar' })).toBeInTheDocument()
  })

  it('removes a watch from the list', async () => {
    const fetch = watchApi([watch()], () => new Response(null, { status: 204 }))
    renderWithProviders(<ImportsPage />)

    await userEvent.click(await within(panel()).findByRole('button', { name: 'Parar de observar live.log' }))

    expect(fetch.mock.calls.find(([, init]) => init?.method === 'DELETE')?.[0]).toBe('http://localhost:8000/watches/1')
    expect(within(panel()).queryByRole('list', { name: 'Arquivos observados' })).not.toBeInTheDocument()
  })
})

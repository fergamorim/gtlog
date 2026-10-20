import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ImportJob } from '../api/types'
import { json, mockFetch, renderWithProviders } from '../test/utils'
import { ImportsPage } from './ImportsPage'

function uploadApi(response: () => Response) {
  return mockFetch((url, init) => {
    if (url.pathname === '/imports' && init?.method === 'POST') return response()
    if (url.pathname === '/imports') return json([])
    return json({ detail: 'não encontrado' }, 404)
  })
}

const file = (content = '2026-10-05T17:46:57Z INFO [auth] ok\n', name = 'app.log') => new File([content], name, { type: 'text/plain' })

describe('ImportsPage upload', () => {
  it.each([
    [413, 'O arquivo excede o tamanho máximo permitido de 200 MB.'],
    [415, 'O arquivo parece ser binário. Envie um log em texto.'],
    [422, 'O arquivo está vazio.'],
  ])('shows the API detail message on HTTP %i', async (status, detail) => {
    const fetch = uploadApi(() => json({ detail }, status))
    renderWithProviders(<ImportsPage />)

    await userEvent.upload(screen.getByLabelText('Arquivo de log'), file())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(detail)
    expect(alert).toHaveTextContent('Não foi possível importar app.log')
    const post = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
    expect(post?.[1]?.body).toBeInstanceOf(FormData)
  })

  it('falls back to a status message when the error body has no detail', async () => {
    uploadApi(() => new Response('<html>Request Entity Too Large</html>', { status: 413 }))
    renderWithProviders(<ImportsPage />)

    await userEvent.upload(screen.getByLabelText('Arquivo de log'), file())

    expect(await screen.findByRole('alert')).toHaveTextContent('O arquivo excede o tamanho máximo permitido.')
  })

  it('rejects an empty file before uploading', async () => {
    const fetch = uploadApi(() => json({}, 500))
    renderWithProviders(<ImportsPage />)

    await userEvent.upload(screen.getByLabelText('Arquivo de log'), file(''))

    expect(await screen.findByRole('alert')).toHaveTextContent('O arquivo está vazio')
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('accepts CSV files and mentions them in the hint', async () => {
    const fetch = uploadApi(() => json({ detail: 'erro' }, 422))
    renderWithProviders(<ImportsPage />)

    expect(screen.getByText(/CSV com cabeçalho/)).toBeInTheDocument()
    const csv = new File(['timestamp,level,message\n2026-10-05T17:46:57Z,INFO,ok\n'], 'export.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByLabelText('Arquivo de log'), csv)

    await screen.findByRole('alert')
    const post = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
    expect((post?.[1]?.body as FormData).get('file')).toBe(csv)
  })

  it('shows import progress after a successful upload', async () => {
    const job: ImportJob = {
      id: 9, filename: 'app.log', status: 'DONE', format: 'text', total_lines: 10, parsed_lines: 9, invalid_lines: 1,
      error: null, created_at: '2026-10-05T17:00:00Z', finished_at: '2026-10-05T17:00:02Z',
    }
    mockFetch((url, init) => {
      if (url.pathname === '/imports' && init?.method === 'POST') return json({ ...job, status: 'PENDING' }, 202)
      if (url.pathname === '/imports/9') return json(job)
      return json([job])
    })
    renderWithProviders(<ImportsPage />)

    await userEvent.upload(screen.getByLabelText('Arquivo de log'), file())

    expect(await screen.findByText(/Importação concluída/, {}, { timeout: 3000 })).toBeInTheDocument()
    const panel = screen.getByRole('region', { name: 'Novo arquivo' })
    expect(within(panel).getByRole('link', { name: /Ver logs/ })).toHaveAttribute('href', '/logs?import_id=9')
    expect(within(panel).getByText('Concluída')).toBeInTheDocument()
  })
})

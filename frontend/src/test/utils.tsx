import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

export function renderWithProviders(ui: ReactElement, { route = '/' }: { route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response>

/** Replaces global fetch; the handler receives the parsed URL. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url)
    return Promise.resolve(handler(url, init))
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export const EMPTY_STATS = {
  total: 0,
  by_level: { DEBUG: 0, INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0 },
  error_rate: 0,
  first_timestamp: null,
  last_timestamp: null,
  bucket: 'hour',
  timeseries: [],
  by_service: [],
  by_category: [],
  top_errors: [],
}

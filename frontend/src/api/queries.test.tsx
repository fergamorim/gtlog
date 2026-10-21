import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { json, mockFetch } from '../test/utils'
import { queryKeys, useImportCompletionWatcher, useWatchActivity } from './queries'
import type { ImportJob, LogWatch } from './types'

const job = (status: ImportJob['status']): ImportJob => ({
  id: 1, filename: 'app.log', status, format: 'text', total_lines: 10, parsed_lines: 10, invalid_lines: 0,
  error: null, created_at: '2026-10-05T17:00:00Z', finished_at: status === 'DONE' ? '2026-10-05T17:00:02Z' : null,
})

describe('useImportCompletionWatcher', () => {
  it('refreshes logs, counts, stats and facets when a job finishes, on any page', async () => {
    let status: ImportJob['status'] = 'PROCESSING'
    mockFetch(() => json([job(status)]))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const reset = vi.spyOn(client, 'resetQueries')
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>

    renderHook(() => useImportCompletionWatcher(), { wrapper })
    await waitFor(() => expect(client.getQueryData<ImportJob[]>(queryKeys.imports)?.[0].status).toBe('PROCESSING'))
    expect(reset).not.toHaveBeenCalled()

    status = 'DONE'
    await client.refetchQueries({ queryKey: queryKeys.imports })

    await waitFor(() => expect(reset).toHaveBeenCalledWith({ queryKey: ['logs'] }))
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey?.[0])
    expect(keys).toEqual(expect.arrayContaining(['logCount', 'stats', 'facets', 'imports']))
  })

  it('does not refresh for jobs that were already finished when first seen', async () => {
    mockFetch(() => json([job('DONE')]))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const reset = vi.spyOn(client, 'resetQueries')
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>

    renderHook(() => useImportCompletionWatcher(), { wrapper })
    await waitFor(() => expect(client.getQueryData(queryKeys.imports)).toBeDefined())
    await client.refetchQueries({ queryKey: queryKeys.imports })
    expect(reset).not.toHaveBeenCalled()
  })
})

describe('useWatchActivity', () => {
  const watch = (parsed: number): LogWatch => ({
    id: 1, path: 'live.log', interval_seconds: 5, active: true, import_id: 3, format: 'text', offset: 0,
    parsed_lines: parsed, invalid_lines: 0, last_error: null, critical_lines: 0, last_critical_message: null, last_critical_at: null,
    created_at: '2026-10-05T17:00:00Z',
    last_checked_at: null, next_check_at: '2026-10-05T17:00:00Z',
  })

  it('refreshes the data views when a watch imports new lines, keeping deep-scrolled logs', async () => {
    let parsed = 5
    mockFetch(() => json([watch(parsed)]))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['logs', 'a'], { pages: [{}], pageParams: [null] })
    client.setQueryData(['logs', 'b'], { pages: [{}, {}], pageParams: [null, 'x'] })
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>

    renderHook(() => useWatchActivity(), { wrapper })
    await waitFor(() => expect(client.getQueryData<LogWatch[]>(queryKeys.watches)?.[0].parsed_lines).toBe(5))
    await client.refetchQueries({ queryKey: queryKeys.watches })
    expect(invalidate).not.toHaveBeenCalled()

    parsed = 8
    await client.refetchQueries({ queryKey: queryKeys.watches })

    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['stats'] }))
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey)
    expect(keys).toEqual(expect.arrayContaining([['logs', 'a'], ['logCount'], ['facets'], ['imports']]))
    expect(keys).not.toContainEqual(['logs', 'b'])
  })
})

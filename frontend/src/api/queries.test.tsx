import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { json, mockFetch } from '../test/utils'
import { queryKeys, useImportCompletionWatcher } from './queries'
import type { ImportJob } from './types'

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

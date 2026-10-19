import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { useEffect, useMemo, useRef } from 'react'
import { toParams, type FilterKey, type LogFilters } from '../lib/filters'
import { api } from './client'
import type { ImportJob, LogEntry, LogPage } from './types'

export const LOGS_PAGE_SIZE = 200

export const queryKeys = {
  health: ['health'] as const,
  imports: ['imports'] as const,
  importJob: (id: number) => ['imports', id] as const,
  logs: (params: string) => ['logs', params] as const,
  log: (id: number) => ['log', id] as const,
  facets: ['facets'] as const,
  stats: (params: string) => ['stats', params] as const,
}

export const isJobFinished = (job?: ImportJob) => job?.status === 'DONE' || job?.status === 'FAILED'

export function useApiHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 30_000,
    retry: false,
  })
}

/* ------------------------------- Imports -------------------------------- */

export function useImports() {
  return useQuery({
    queryKey: queryKeys.imports,
    queryFn: ({ signal }) => api.listImports(signal),
    // Keep the list live while any import is still running.
    refetchInterval: (query) => (query.state.data?.some((job) => !isJobFinished(job)) ? 2000 : false),
  })
}

/** Called once an import finishes: new rows exist, so cached logs, stats and facets are stale. */
function refreshAfterImport(client: QueryClient) {
  // Reset (not invalidate) logs: refetching every loaded page of an infinite list would be wasteful.
  client.resetQueries({ queryKey: ['logs'] })
  client.invalidateQueries({ queryKey: ['stats'] })
  client.invalidateQueries({ queryKey: queryKeys.facets })
  client.invalidateQueries({ queryKey: queryKeys.imports, exact: true })
}

/** Polls an import every second until it is DONE or FAILED. */
export function useImportJob(id: number | null) {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: queryKeys.importJob(id ?? 0),
    queryFn: ({ signal }) => api.getImport(id!, signal),
    enabled: id != null,
    refetchInterval: (q) => (isJobFinished(q.state.data) ? false : 1000),
    refetchIntervalInBackground: true,
  })

  const status = query.data?.status
  const previous = useRef(status)
  useEffect(() => {
    if (previous.current && previous.current !== status && isJobFinished(query.data)) refreshAfterImport(client)
    previous.current = status
  }, [status, query.data, client])

  return query
}

export function useUploadImport() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => api.uploadImport(file),
    onSuccess: (job) => {
      client.setQueryData(queryKeys.importJob(job.id), job)
      client.setQueryData<ImportJob[]>(queryKeys.imports, (list) => [job, ...(list ?? []).filter((j) => j.id !== job.id)])
    },
  })
}

/* --------------------------------- Logs --------------------------------- */

/** Stable string form of the filters, used both as query key and request params. */
export function useFilterParams(filters: LogFilters, keys?: FilterKey[]): string {
  return useMemo(() => toParams(filters, keys).toString(), [filters, keys])
}

export function useLogs(filters: LogFilters) {
  const params = useFilterParams(filters)
  return useInfiniteQuery({
    queryKey: queryKeys.logs(params),
    queryFn: ({ pageParam, signal }) => api.listLogs(new URLSearchParams(params), pageParam, LOGS_PAGE_SIZE, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (last: LogPage) => last.next_cursor ?? undefined,
    // Keep current rows visible (dimmed) while a new filter loads instead of flashing a skeleton.
    placeholderData: keepPreviousData,
    // Refetching hundreds of loaded pages on focus would be expensive; logs are immutable once imported.
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
}

export function useLog(id: number | null, fallback?: LogEntry) {
  return useQuery({
    queryKey: queryKeys.log(id ?? 0),
    queryFn: ({ signal }) => api.getLog(id!, signal),
    enabled: id != null && !fallback,
    initialData: fallback,
    staleTime: Infinity,
  })
}

export function useFacets() {
  return useQuery({
    queryKey: queryKeys.facets,
    queryFn: ({ signal }) => api.getFacets(signal),
    staleTime: 5 * 60_000,
  })
}

/* -------------------------------- Stats --------------------------------- */

export function useStats(filters: LogFilters, keys?: FilterKey[]) {
  const params = useFilterParams(filters, keys)
  return useQuery({
    queryKey: queryKeys.stats(params),
    queryFn: ({ signal }) => api.getStats(new URLSearchParams(params), signal),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

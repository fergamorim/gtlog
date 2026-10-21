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
import type { Bucket, ImportJob, ImportStatus, LogEntry, LogPage, LogWatch, LogWatchInput } from './types'

export const LOGS_PAGE_SIZE = 200

export const queryKeys = {
  health: ['health'] as const,
  imports: ['imports'] as const,
  importJob: (id: number) => ['imports', id] as const,
  logs: (params: string) => ['logs', params] as const,
  logCount: (params: string) => ['logCount', params] as const,
  log: (id: number) => ['log', id] as const,
  facets: ['facets'] as const,
  stats: (params: string) => ['stats', params] as const,
  watches: ['watches'] as const,
  watchSettings: ['watchSettings'] as const,
  watchFolder: (path: string) => ['watchFolder', path] as const,
}

const isStatusFinished = (status: ImportStatus) => status === 'DONE' || status === 'FAILED'
export const isJobFinished = (job?: ImportJob) => job != null && isStatusFinished(job.status)

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
  client.invalidateQueries({ queryKey: ['logCount'] })
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

  // Mirror the polled job into the list so the global watcher sees the transition without waiting for its own poll.
  const job = query.data
  useEffect(() => {
    if (!job) return
    client.setQueryData<ImportJob[]>(queryKeys.imports, (list) => list?.map((j) => (j.id === job.id ? job : j)))
  }, [job, client])

  return query
}

/**
 * Mounted once in App: watches the imports list (which polls while any job runs) and refreshes
 * logs, counts, stats and facets when a job finishes, whatever page the user is on.
 */
export function useImportCompletionWatcher() {
  const client = useQueryClient()
  const { data } = useImports()
  const previous = useRef(new Map<number, ImportStatus>())

  useEffect(() => {
    if (!data) return
    const finished = data.some((job) => {
      const before = previous.current.get(job.id)
      return before !== undefined && !isStatusFinished(before) && isStatusFinished(job.status)
    })
    previous.current = new Map(data.map((job) => [job.id, job.status]))
    if (finished) refreshAfterImport(client)
  }, [data, client])
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

/* -------------------------------- Watches -------------------------------- */

export const WATCH_REFRESH_MS = 3000

export function useWatches() {
  return useQuery({
    queryKey: queryKeys.watches,
    queryFn: ({ signal }) => api.listWatches(signal),
    // New lines can arrive at any time while a watch is active.
    refetchInterval: (query) => (query.state.data?.some((watch) => watch.active) ? WATCH_REFRESH_MS : false),
  })
}

export function useWatchSettings() {
  return useQuery({
    queryKey: queryKeys.watchSettings,
    queryFn: ({ signal }) => api.getWatchSettings(signal),
    staleTime: Infinity,
  })
}

/** One folder of the watch root, for the file picker; always fresh, files keep changing. */
export function useWatchFolder(path: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.watchFolder(path),
    queryFn: ({ signal }) => api.listWatchFolder(path, signal),
    enabled,
    staleTime: 0,
  })
}

/** Create, pause/resume and delete watches; each one updates the cached list right away. */
export function useWatchMutations() {
  const client = useQueryClient()
  const setList = (update: (list: LogWatch[]) => LogWatch[]) =>
    client.setQueryData<LogWatch[]>(queryKeys.watches, (list) => update(list ?? []))
  return {
    create: useMutation({
      mutationFn: (input: LogWatchInput) => api.createWatch(input),
      onSuccess: (watch) => {
        setList((list) => [watch, ...list])
        client.invalidateQueries({ queryKey: queryKeys.imports, exact: true })
      },
    }),
    setActive: useMutation({
      mutationFn: ({ id, active }: { id: number; active: boolean }) => api.updateWatch(id, { active }),
      onSuccess: (watch) => setList((list) => list.map((w) => (w.id === watch.id ? watch : w))),
    }),
    remove: useMutation({
      mutationFn: (id: number) => api.deleteWatch(id),
      onSuccess: (_, id) => setList((list) => list.filter((w) => w.id !== id)),
    }),
  }
}

/**
 * New lines from a watch: refresh counts, stats, facets and imports. A logs list is refetched only
 * while it has a single page loaded, so a user scrolled deep into the table is not thrown back to the top.
 */
function refreshAfterWatch(client: QueryClient) {
  for (const query of client.getQueryCache().findAll({ queryKey: ['logs'] })) {
    const pages = (query.state.data as { pages?: unknown[] } | undefined)?.pages
    if (!pages || pages.length <= 1) client.invalidateQueries({ queryKey: query.queryKey, exact: true })
  }
  client.invalidateQueries({ queryKey: ['logCount'] })
  client.invalidateQueries({ queryKey: ['stats'] })
  client.invalidateQueries({ queryKey: queryKeys.facets })
  client.invalidateQueries({ queryKey: queryKeys.imports })
}

/** Mounted once in App: refreshes the data views whenever an active watch imports new lines. */
export function useWatchActivity() {
  const client = useQueryClient()
  const { data } = useWatches()
  const previous = useRef(new Map<number, number>())

  useEffect(() => {
    if (!data) return
    const grew = data.some((watch) => {
      const before = previous.current.get(watch.id)
      return before !== undefined && watch.parsed_lines + watch.invalid_lines > before
    })
    previous.current = new Map(data.map((watch) => [watch.id, watch.parsed_lines + watch.invalid_lines]))
    if (grew) refreshAfterWatch(client)
  }, [data, client])
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

/** Total matching the filters (GET /logs/count), shown next to the loaded-rows counter. */
export function useLogCount(filters: LogFilters) {
  const params = useFilterParams(filters)
  return useQuery({
    queryKey: queryKeys.logCount(params),
    queryFn: ({ signal }) => api.countLogs(new URLSearchParams(params), signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
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

/** Dashboard aggregates; `bucket` forces hourly or daily points (default: picked by the API from the period). */
export function useStats(filters: LogFilters, keys?: FilterKey[], bucket?: Bucket) {
  const filterParams = useFilterParams(filters, keys)
  const params = bucket ? `${filterParams}${filterParams ? '&' : ''}bucket=${bucket}` : filterParams
  return useQuery({
    queryKey: queryKeys.stats(params),
    queryFn: ({ signal }) => api.getStats(new URLSearchParams(params), signal),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

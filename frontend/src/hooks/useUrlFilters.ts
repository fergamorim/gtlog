import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EMPTY_FILTERS, parseFilters, writeFilters, type FilterKey, type LogFilters } from '../lib/filters'

/**
 * Filters live in the URL so views are shareable and survive reloads.
 * Updates replace the current history entry, so Back leaves the page instead of undoing each keystroke.
 */
export function useUrlFilters() {
  const [params, setParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(params), [params])

  /**
   * Applies `patch` in a single URL update. `drop` removes non-filter params in the same update
   * (e.g. `log` to close the drawer): two setSearchParams calls in one tick would see the same stale params.
   */
  const setFilters = useCallback(
    (patch: Partial<LogFilters>, options?: { drop?: string[] }) => {
      setParams(
        (prev) => {
          const next = writeFilters(prev, { ...parseFilters(prev), ...patch })
          options?.drop?.forEach((key) => next.delete(key))
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  /** Clears the given filter keys (all when omitted). */
  const clearFilters = useCallback(
    (keys?: FilterKey[]) => {
      setParams(
        (prev) => {
          const current = parseFilters(prev)
          const next = keys
            ? { ...current, ...Object.fromEntries(keys.map((key) => [key, EMPTY_FILTERS[key]])) }
            : EMPTY_FILTERS
          return writeFilters(prev, next)
        },
        { replace: true },
      )
    },
    [setParams],
  )

  return { filters, setFilters, clearFilters }
}

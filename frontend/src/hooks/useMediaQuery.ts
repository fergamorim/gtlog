import { useSyncExternalStore } from 'react'

/** Subscribes to a CSS media query; returns false where matchMedia is unavailable (tests, SSR). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      if (typeof window.matchMedia !== 'function') return () => {}
      const list = window.matchMedia(query)
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => (typeof window.matchMedia === 'function' ? window.matchMedia(query).matches : false),
  )
}

/** Below this width the logs table collapses into cards (keep in sync with index.css). */
export const COMPACT_QUERY = '(max-width: 699px)'

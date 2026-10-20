import { useCallback, useState } from 'react'

export type Theme = 'light' | 'dark'
const STORAGE_KEY = 'gtlog-theme'

/** Theme is resolved before paint in index.html; this hook only reads and toggles it. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  )

  const toggle = useCallback(() => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Storage may be unavailable (private mode); the choice just won't persist.
    }
    setTheme(next)
  }, [theme])

  return { theme, toggle }
}

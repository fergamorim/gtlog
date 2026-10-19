import type { CSSProperties } from 'react'
import { LEVELS, type Level } from '../api/types'

/**
 * Single source of truth for level colors. Values are CSS variables from index.css,
 * so badges, chips and charts switch with the theme and never drift apart.
 */
export const LEVEL_META: Record<Level, { label: string; color: string; soft: string; fg: string }> = {
  DEBUG: { label: 'Debug', color: 'var(--level-debug)', soft: 'var(--level-debug-soft)', fg: 'var(--level-debug-fg)' },
  INFO: { label: 'Info', color: 'var(--level-info)', soft: 'var(--level-info-soft)', fg: 'var(--level-info-fg)' },
  WARNING: { label: 'Warning', color: 'var(--level-warning)', soft: 'var(--level-warning-soft)', fg: 'var(--level-warning-fg)' },
  ERROR: { label: 'Error', color: 'var(--level-error)', soft: 'var(--level-error-soft)', fg: 'var(--level-error-fg)' },
  CRITICAL: { label: 'Critical', color: 'var(--level-critical)', soft: 'var(--level-critical-soft)', fg: 'var(--level-critical-fg)' },
}

export const ERROR_LEVELS: Level[] = ['ERROR', 'CRITICAL']

/** Levels from most to least severe (tooltips, legends that rank severity). */
export const LEVELS_BY_SEVERITY: Level[] = [...LEVELS].reverse()

/** Inline custom properties consumed by `.level-badge`, `.chip`, `.dist__bar`, etc. */
export function levelVars(level: Level): CSSProperties {
  const meta = LEVEL_META[level]
  return { '--lvl': meta.color, '--lvl-soft': meta.soft, '--lvl-fg': meta.fg } as CSSProperties
}

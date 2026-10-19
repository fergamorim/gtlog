import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { EMPTY_FILTERS, parseFilters, writeFilters, type LogFilters } from '../lib/filters'
import { useUrlFilters } from './useUrlFilters'

function setup(route: string) {
  const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
  return renderHook(() => ({ ...useUrlFilters(), location: useLocation() }), { wrapper })
}

const FULL: LogFilters = {
  level: ['ERROR', 'CRITICAL'],
  service: ['payments', 'auth'],
  category: ['timeout'],
  importId: 3,
  start: '2026-10-01T00:00:00.000Z',
  end: '2026-10-02T00:00:00.000Z',
  q: 'timeout calling',
}

describe('filters <-> URL', () => {
  it('round-trips every filter through the query string', () => {
    const params = writeFilters(new URLSearchParams(), FULL)
    expect(parseFilters(new URLSearchParams(params.toString()))).toEqual(FULL)
  })

  it('ignores invalid values from hand-edited URLs', () => {
    const parsed = parseFilters(new URLSearchParams('level=FOO&level=error&import_id=abc&start=ontem&q=%20%20'))
    expect(parsed).toEqual({ ...EMPTY_FILTERS, level: ['ERROR'] })
  })
})

describe('useUrlFilters', () => {
  it('reads filters from the URL', () => {
    const { result } = setup('/logs?level=ERROR&level=CRITICAL&service=payments&service=auth&category=timeout&import_id=3&start=2026-10-01T00:00:00.000Z&end=2026-10-02T00:00:00.000Z&q=timeout+calling')
    expect(result.current.filters).toEqual(FULL)
  })

  it('writes a patch to the URL, keeping other filters and unrelated params', () => {
    const { result } = setup('/logs?level=ERROR&log=42')

    act(() => result.current.setFilters({ service: ['payments'], q: 'timeout' }))

    const params = new URLSearchParams(result.current.location.search)
    expect(params.getAll('level')).toEqual(['ERROR'])
    expect(params.getAll('service')).toEqual(['payments'])
    expect(params.get('q')).toBe('timeout')
    expect(params.get('log')).toBe('42')
    expect(result.current.filters).toEqual({ ...EMPTY_FILTERS, level: ['ERROR'], service: ['payments'], q: 'timeout' })
  })

  it('round-trips a full filter set through setFilters and back', () => {
    const { result } = setup('/logs')
    act(() => result.current.setFilters(FULL))
    expect(parseFilters(new URLSearchParams(result.current.location.search))).toEqual(FULL)
    expect(result.current.filters).toEqual(FULL)
  })

  it('clears all or only some filters', () => {
    const { result } = setup('/dashboard?level=ERROR&service=auth&import_id=2&log=7')

    act(() => result.current.clearFilters(['service', 'importId']))
    expect(result.current.filters).toEqual({ ...EMPTY_FILTERS, level: ['ERROR'] })

    act(() => result.current.clearFilters())
    expect(result.current.filters).toEqual(EMPTY_FILTERS)
    expect(result.current.location.search).toBe('?log=7')
  })
})

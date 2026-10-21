import { describe, expect, it } from 'vitest'
import { levelForStatus, normalizeStatus, statusLevels, statusOptions } from './status'

describe('levelForStatus (tabela "Códigos HTTP e níveis" de docs/api.md)', () => {
  it.each([
    [100, 'DEBUG'],
    [101, 'DEBUG'],
    [200, 'INFO'],
    [201, 'INFO'],
    [204, 'INFO'],
    [301, 'INFO'],
    [304, 'INFO'],
    [400, 'WARNING'],
    [401, 'WARNING'],
    [403, 'WARNING'],
    [404, 'WARNING'],
    [429, 'WARNING'],
    [500, 'ERROR'],
    [501, 'ERROR'],
    [505, 'ERROR'],
    [599, 'ERROR'],
    [502, 'CRITICAL'],
    [503, 'CRITICAL'],
    [504, 'CRITICAL'],
    ['1xx', 'DEBUG'],
    ['2xx', 'INFO'],
    ['3xx', 'INFO'],
    ['4xx', 'WARNING'],
    ['5XX', 'ERROR'],
    ['503', 'CRITICAL'],
  ] as const)('%s -> %s', (status, level) => {
    expect(levelForStatus(status)).toBe(level)
  })

  it.each([null, undefined, 99, 600, 0, '6xx', 'abc', '40'])('%s has no level', (status) => {
    expect(levelForStatus(status)).toBeNull()
  })

  it('shows ERROR and CRITICAL for the 5xx class', () => {
    expect(statusLevels('5xx')).toEqual(['ERROR', 'CRITICAL'])
    expect(statusLevels('404')).toEqual(['WARNING'])
    expect(statusLevels('foo')).toEqual([])
  })
})

describe('normalizeStatus', () => {
  it.each([
    ['404', '404'],
    [' 5XX ', '5xx'],
    ['100', '100'],
    ['599', '599'],
    ['600', null],
    ['099', null],
    ['4x', null],
    ['', null],
  ])('%j -> %j', (value, expected) => {
    expect(normalizeStatus(value)).toBe(expected)
  })
})

describe('statusOptions', () => {
  it('lists classes 2xx..5xx then the sorted distinct codes', () => {
    expect(statusOptions([500, 200, 404, 200])).toEqual(['2xx', '3xx', '4xx', '5xx', '200', '404', '500'])
  })

  it('includes 1xx only when such codes exist', () => {
    expect(statusOptions([101, 200])).toEqual(['1xx', '2xx', '3xx', '4xx', '5xx', '101', '200'])
    expect(statusOptions([])).toEqual(['2xx', '3xx', '4xx', '5xx'])
  })
})

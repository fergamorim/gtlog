import { describe, expect, it } from 'vitest'
import { formatBucket, formatDateTime, formatTimestamp, isoToLocalInput, localInputToIso, spansYears } from './format'

// These hold in any machine time zone: the UI always shows UTC (run with TZ=America/Sao_Paulo to check).
describe('dates are shown in UTC', () => {
  it('keeps a timestamp as written in a file without a zone', () => {
    expect(formatTimestamp('2016-02-29T01:23:00Z')).toBe('29/02/2016, 01:23:00,000')
    expect(formatDateTime('2016-02-29T01:23:00Z')).toBe('29/02/2016, 01:23')
  })

  it('labels a daily bucket with its own day, not the previous one', () => {
    expect(formatBucket('2016-02-29T00:00:00Z', 'day')).toBe('29/02')
    expect(formatBucket('2016-02-29T00:00:00Z', 'day', true)).toBe('29/02/16')
    expect(formatBucket('2016-02-29T13:00:00Z', 'hour')).toBe('29/02, 13:00')
  })

  it('round-trips the period inputs as UTC', () => {
    expect(isoToLocalInput('2016-02-29T01:23:00.000Z')).toBe('2016-02-29T01:23')
    expect(localInputToIso('2016-02-29T01:23')).toBe('2016-02-29T01:23:00.000Z')
    expect(localInputToIso('')).toBeNull()
    expect(isoToLocalInput('nope')).toBe('')
  })
})

describe('spansYears', () => {
  it('is true only when the buckets cross a calendar year', () => {
    expect(spansYears(['2016-02-29T00:00:00Z', '2017-02-15T00:00:00Z'])).toBe(true)
    expect(spansYears(['2018-01-02T00:00:00Z', '2018-12-15T00:00:00Z'])).toBe(false)
    expect(spansYears(['2018-01-02T00:00:00Z'])).toBe(false)
  })
})

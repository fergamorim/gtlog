import { describe, expect, it } from 'vitest'
import { dayRange, formatBucket, formatBucketTitle, formatDateTime, formatDay, formatHour, formatInterval, shiftDay, utcDay, formatTimestamp, isoToLocalInput, localInputToIso, spansYears } from './format'

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

describe('formatInterval', () => {
  it.each([
    [1, '1 s'],
    [45, '45 s'],
    [60, '1 min'],
    [90, '1 min e 30 s'],
    [600, '10 min'],
    [3600, '1 h'],
    [86_400, '24 h'],
  ])('formats %i seconds as %s', (seconds, text) => {
    expect(formatInterval(seconds)).toBe(text)
  })
})

describe('day helpers (UTC)', () => {
  it('finds the UTC day of an instant and its [start, end) range', () => {
    expect(utcDay('2026-10-05T23:59:59-03:00')).toBe('2026-10-06')
    expect(dayRange('2026-10-05')).toEqual({ start: '2026-10-05T00:00:00.000Z', end: '2026-10-06T00:00:00.000Z' })
  })

  it('moves across month and year ends', () => {
    expect(shiftDay('2026-10-31', 1)).toBe('2026-11-01')
    expect(shiftDay('2027-01-01', -1)).toBe('2026-12-31')
  })

  it('formats the day and the hour', () => {
    expect(formatDay('2026-10-05')).toBe('05/10/2026')
    expect(formatHour('2026-10-05T07:00:00Z')).toBe('07:00')
  })
})

describe('fine-grained buckets', () => {
  it('labels seconds with the clock and minutes with date and time', () => {
    expect(formatBucket('2026-10-21T14:33:17Z', 'second')).toBe('14:33:17')
    expect(formatBucket('2026-10-21T14:33:00Z', 'minute')).toBe('21/10, 14:33')
    expect(formatBucketTitle('2026-10-21T14:33:17Z', 'second')).toBe('21/10/2026, 14:33:17')
  })

  it('keeps seconds in the period inputs only when they are set', () => {
    expect(isoToLocalInput('2026-10-21T14:33:17Z')).toBe('2026-10-21T14:33:17')
    expect(isoToLocalInput('2026-10-21T14:33:00Z')).toBe('2026-10-21T14:33')
    expect(localInputToIso('2026-10-21T14:33:17')).toBe('2026-10-21T14:33:17.000Z')
  })
})

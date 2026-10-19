import { describe, expect, it } from 'vitest'
import { messageToQuery } from './filters'

describe('messageToQuery', () => {
  it.each([
    ['timeout calling auth after #ms', '"timeout calling auth after"'],
    ['payment # declined', '"payment" "declined"'],
    ['database connection refused', '"database connection refused"'],
    ['say "hello" #', '"say hello"'],
    ['# #', ''],
  ])('%s -> %s', (message, query) => {
    expect(messageToQuery(message)).toBe(query)
  })
})

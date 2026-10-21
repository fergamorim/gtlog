// [TESTE] Falha proposital para validar a proteção de branch. Não mergear.
import { describe, expect, it } from 'vitest'

describe('ci gate', () => {
  it('falha de propósito', () => {
    expect(1 + 1).toBe(3)
  })
})

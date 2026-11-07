import { describe, expect, it } from 'vitest'
import {
  clearProviderKeys, getAdminToken, getProviderKey, rememberKeys, setAdminToken, setProviderKey, setRememberKeys,
} from './session'

describe('secret handling', () => {
  it('keeps model keys in memory only by default', () => {
    setProviderKey('openai', 'sk-secret')
    expect(getProviderKey('openai')).toBe('sk-secret')
    expect(sessionStorage.length).toBe(0)
    expect(localStorage.length).toBe(0)
  })

  it('stores keys in this tab only when the user opts in, and never in localStorage', () => {
    setProviderKey('openai', 'sk-secret')
    setRememberKeys(true)
    expect(rememberKeys()).toBe(true)
    expect(sessionStorage.getItem('llmops.keys')).toContain('sk-secret')
    setProviderKey('gemini', 'g-key')
    expect(sessionStorage.getItem('llmops.keys')).toContain('g-key')
    expect(localStorage.length).toBe(0)
  })

  it('clears everything on request', () => {
    setProviderKey('openai', 'sk-secret'); setRememberKeys(true)
    clearProviderKeys()
    expect(getProviderKey('openai')).toBe('')
    expect(sessionStorage.getItem('llmops.keys')).toBeNull()
    expect(rememberKeys()).toBe(false)
  })

  it('keeps the admin token in session storage, not local storage', () => {
    setAdminToken('tok')
    expect(getAdminToken()).toBe('tok')
    expect(sessionStorage.getItem('llmops.admin')).toBe('tok')
    expect(localStorage.getItem('llmops.admin')).toBeNull()
    setAdminToken('')
    expect(getAdminToken()).toBe('')
  })
})

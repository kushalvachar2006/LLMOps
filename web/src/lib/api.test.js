import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { setAdminToken } from './session'
import { json, mockApi } from '../test/utils'

describe('api client', () => {
  it('sends the model key as a header only, never in the URL or body', async () => {
    const calls = mockApi({ 'POST /api/generate': { ok: true } })
    await api.generate({ prompt: 'hi', provider: 'openai' }, 'sk-user-key')
    expect(calls[0].headers['X-Provider-Api-Key']).toBe('sk-user-key')
    expect(JSON.stringify(calls[0].body)).not.toContain('sk-user-key')
    expect(JSON.stringify(calls[0].query)).not.toContain('sk-user-key')
  })

  it('adds the admin token to /api calls but not to the public /v1 endpoint', async () => {
    setAdminToken('admin-123')
    const calls = mockApi({ 'GET /api/projects': { items: [] }, 'POST /v1/deployments/d1/invoke': { output: 'x' } })
    await api.projects.list()
    await api.invoke('d1', { a: '1' }, 'production', 'llmops_key')
    expect(calls[0].headers['X-Admin-Token']).toBe('admin-123')
    expect(calls[1].headers['X-Admin-Token']).toBeUndefined()
    expect(calls[1].headers.Authorization).toBe('Bearer llmops_key')
  })

  it('omits empty query parameters', async () => {
    const calls = mockApi({ 'GET /api/requests': { items: [] } })
    await api.requests({ project_id: undefined, provider: '', limit: 5, model: null })
    expect(calls[0].query).toEqual({ limit: '5' })
  })

  it('turns backend errors into ApiError with category, request id and Retry-After', async () => {
    mockApi({ 'POST /v1/deployments/d1/invoke': () => json({ error: { category: 'rate_limited', message: 'Slow down.', request_id: 'abc' } }, 429, { 'Retry-After': '12' }) })
    const err = await api.invoke('d1', {}, 'production', 'k').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.category).toBe('rate_limited')
    expect(err.status).toBe(429)
    expect(err.message).toContain('Retry after 12 seconds')
    expect(err.requestId).toBe('abc')
  })

  it('reports an unreachable backend in plain words', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    const err = await api.health().catch((e) => e)
    expect(err.category).toBe('unreachable')
    expect(err.message).toMatch(/backend running/)
  })

  it('announces when the server asks for an admin token', async () => {
    const seen = vi.fn()
    window.addEventListener('llmops:auth-required', seen)
    mockApi({ 'GET /api/projects': () => json({ error: { category: 'unauthorized', message: 'Missing or invalid admin token.' } }, 401) })
    await api.projects.list().catch(() => {})
    window.removeEventListener('llmops:auth-required', seen)
    expect(seen).toHaveBeenCalledTimes(1)
  })

  it('handles empty 204 responses', async () => {
    mockApi({ 'DELETE /api/projects/p1': () => json(null, 204) })
    expect(await api.projects.remove('p1')).toBeNull()
  })
})

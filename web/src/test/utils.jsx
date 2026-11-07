import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import App from '../App'
import { ThemeProvider, ToastProvider } from '../context/providers'

export const json = (body, status = 200, headers = {}) =>
  new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })

export const PROJECTS = { items: [{ id: 'p1', name: 'Support Bot', description: 'demo', created_at: '2026-10-01T10:00:00', updated_at: '2026-10-01T10:00:00' }], total: 1, skip: 0, limit: 100 }
export const CATALOG = {
  default_provider: 'mock',
  providers: [
    { id: 'mock', label: 'Mock (offline demo)', server_key_configured: false, models: [{ id: 'mock-model', label: 'Mock model', supports_temperature: true, temp_max: 2, max_output_tokens: 8192, note: '' }] },
    { id: 'openai', label: 'OpenAI', server_key_configured: false, models: [
      { id: 'gpt-4.1-mini', label: 'GPT-4.1 mini', supports_temperature: true, temp_max: 2, max_output_tokens: 8192, note: '' },
      { id: 'gpt-5', label: 'GPT-5', supports_temperature: false, temp_max: 2, max_output_tokens: 8192, note: 'Fixed temperature.' }] },
  ],
}
export const GEN = { request_id: 'req1', text: 'hello back', provider: 'openai', model: 'gpt-4.1-mini', latency_ms: 12, telemetry_recorded: true,
  usage: { input_tokens: 3, output_tokens: 4, total_tokens: 7 } }

/** Replaces fetch with a router. Unknown routes answer 404 so a missing mock is obvious. */
export function mockApi(routes = {}) {
  const calls = []
  const table = {
    'GET /health': { status: 'ok', api: { status: 'up' }, database: { status: 'up' }, llm_provider: 'mock', admin_auth: false },
    'GET /api/projects': PROJECTS, 'GET /api/models': CATALOG, ...routes,
  }
  vi.stubGlobal('fetch', vi.fn(async (url, init = {}) => {
    const u = new URL(url, 'http://localhost')
    const call = { method: (init.method || 'GET').toUpperCase(), path: u.pathname, query: Object.fromEntries(u.searchParams),
      headers: init.headers || {}, body: init.body ? JSON.parse(init.body) : undefined }
    calls.push(call)
    const h = table[`${call.method} ${call.path}`]
    if (h === undefined) return json({ error: { category: 'not_found', message: `No mock for ${call.method} ${call.path}` } }, 404)
    const out = typeof h === 'function' ? await h(call) : h
    return out instanceof Response ? out : json(out)
  }))
  return calls
}

export function renderApp(path = '/app') {
  return render(<ThemeProvider><ToastProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></ToastProvider></ThemeProvider>)
}

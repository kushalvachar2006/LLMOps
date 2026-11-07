import { getAdminToken } from './session'

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, category = 'error', status = 0, extra = {}) {
    super(message)
    this.name = 'ApiError'
    this.category = category
    this.status = status
    Object.assign(this, extra)
  }
}

function buildUrl(path, params) {
  const qs = new URLSearchParams()
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  })
  const q = qs.toString()
  return `${BASE}${path}${q ? `?${q}` : ''}`
}

async function request(method, path, { body, params, providerKey, bearer, signal } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  // Secrets travel in headers, never in the URL or the body.
  if (providerKey) headers['X-Provider-Api-Key'] = providerKey
  if (bearer) headers.Authorization = `Bearer ${bearer}`
  else if (path.startsWith('/api')) {
    const admin = getAdminToken()
    if (admin) headers['X-Admin-Token'] = admin
  }
  let res
  try {
    res = await fetch(buildUrl(path, params), {
      method, headers, signal, body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new ApiError('Cannot reach the API. Is the backend running?', 'unreachable')
  }
  if (res.status === 204) return null
  let data = null
  try { data = await res.json() } catch { /* non-JSON error pages fall through below */ }
  if (!res.ok) {
    const e = data?.error || {}
    let message = e.message || `Request failed (HTTP ${res.status}).`
    const retry = res.headers?.get?.('Retry-After')
    if (retry) message += ` Retry after ${retry} seconds.`
    if (res.status === 401 && e.category === 'unauthorized' && path.startsWith('/api')) {
      window.dispatchEvent(new CustomEvent('llmops:auth-required'))
    }
    throw new ApiError(message, e.category || 'error', res.status, { requestId: e.request_id, fields: e.fields })
  }
  return data
}

const get = (path, opts) => request('GET', path, opts)
const post = (path, body, opts) => request('POST', path, { ...opts, body: body ?? {} })

export const api = {
  health: () => get('/health'),
  models: () => get('/api/models'),
  generate: (payload, providerKey) => post('/api/generate', payload, { providerKey }),
  requests: (params) => get('/api/requests', { params }),

  projects: {
    list: (params) => get('/api/projects', { params: { limit: 100, ...params } }),
    create: (b) => post('/api/projects', b),
    update: (id, b) => request('PATCH', `/api/projects/${id}`, { body: b }),
    remove: (id) => request('DELETE', `/api/projects/${id}`),
  },
  prompts: {
    list: (projectId) => get('/api/prompts', { params: { project_id: projectId, limit: 100 } }),
    create: (b) => post('/api/prompts', b),
    versions: (id) => get(`/api/prompts/${id}/versions`),
    addVersion: (id, b) => post(`/api/prompts/${id}/versions`, b),
    compare: (id, a, b) => get(`/api/prompts/${id}/compare`, { params: { a, b } }),
    restore: (id, v) => post(`/api/prompts/${id}/versions/${v}/restore`),
  },
  datasets: {
    list: (projectId) => get('/api/datasets', { params: { project_id: projectId, limit: 100 } }),
    create: (b) => post('/api/datasets', b),
    addVersion: (id, b) => post(`/api/datasets/${id}/versions`, b),
    versions: (id) => get(`/api/datasets/${id}/versions`),
    rows: (id, v, params) => get(`/api/datasets/${id}/versions/${v}/rows`, { params }),
  },
  evaluators: () => get('/api/evaluators'),
  experiments: {
    list: (projectId) => get('/api/experiments', { params: { project_id: projectId, limit: 100 } }),
    run: (b, providerKey) => post('/api/experiments', b, { providerKey }),
    results: (id) => get(`/api/experiments/${id}/results`, { params: { limit: 200 } }),
    compare: (ids) => get('/api/experiments/compare', { params: { ids: ids.join(',') } }),
  },
  monitoring: {
    summary: (f) => get('/api/monitoring/summary', { params: f }),
    timeseries: (f) => get('/api/monitoring/timeseries', { params: f }),
    breakdown: (f) => get('/api/monitoring/breakdown', { params: f }),
    quality: (f) => get('/api/monitoring/quality', { params: f }),
    alerts: (f) => get('/api/monitoring/alerts', { params: f }),
    thresholds: () => get('/api/monitoring/thresholds'),
    saveThresholds: (b) => request('PUT', '/api/monitoring/thresholds', { body: b }),
    policy: () => get('/api/monitoring/policy'),
  },
  pricing: {
    list: () => get('/api/pricing'),
    add: (b) => post('/api/pricing', b),
    remove: (id) => request('DELETE', `/api/pricing/${id}`),
  },
  feedback: {
    add: (b) => post('/api/feedback', b),
    list: (params) => get('/api/feedback', { params }),
  },
  deployments: {
    list: (projectId) => get('/api/deployments', { params: { project_id: projectId } }),
    create: (b) => post('/api/deployments', b),
    versions: (id) => get(`/api/deployments/${id}/versions`),
    publish: (id, b, providerKey) => post(`/api/deployments/${id}/versions`, b, { providerKey }),
    healthCheck: (id, v, providerKey) => post(`/api/deployments/${id}/versions/${v}/health-check`, {}, { providerKey }),
    promote: (id, version, environment) => post(`/api/deployments/${id}/promote`, { version, environment }),
    unpublish: (id, env) => request('DELETE', `/api/deployments/${id}/environments/${env}`),
    events: (id) => get(`/api/deployments/${id}/events`),
    usage: (id) => get(`/api/deployments/${id}/usage`),
  },
  apiKeys: {
    list: (projectId) => get('/api/api-keys', { params: { project_id: projectId } }),
    create: (b) => post('/api/api-keys', b),
    revoke: (id) => post(`/api/api-keys/${id}/revoke`),
  },
  /** Calls the PUBLIC endpoint the same way an outside application would. */
  invoke: (deploymentId, inputs, environment, token) =>
    post(`/v1/deployments/${deploymentId}/invoke`, { inputs, environment }, { bearer: token }),
}

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { api } from '../lib/api'
import { CATALOG, GEN, json, mockApi, PROJECTS, renderApp } from '../test/utils'

const last = (calls, method, path) => [...calls].reverse().find((c) => c.method === method && c.path === path)
const all = (calls, method, path) => calls.filter((c) => c.method === method && c.path === path)

/* ---------------- shell ---------------- */
describe('workspace shell', () => {
  it('shows navigation, the project switcher and a connected badge', async () => {
    mockApi({ 'GET /api/requests': { items: [], total: 0 }, 'GET /api/prompts': { items: [], total: 0 }, 'GET /api/datasets': { items: [], total: 0 },
      'GET /api/experiments': { items: [], total: 0 }, 'GET /api/deployments': [] })
    renderApp('/app')
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    for (const name of ['Overview', 'Playground', 'Prompts', 'Datasets', 'Experiments', 'Evaluations', 'Deployments', 'Monitoring', 'Projects', 'Settings']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument()
    }
    expect(await screen.findByRole('option', { name: 'Support Bot' })).toBeInTheDocument()
    expect(await screen.findByText(/Getting started in "Support Bot"/)).toBeInTheDocument()
  })

  it('reports an offline backend instead of a blank screen', async () => {
    const down = () => { throw new TypeError('down') }
    mockApi({ 'GET /health': down, 'GET /api/projects': down })
    renderApp('/app/projects')
    expect(await screen.findByText('API offline')).toBeInTheDocument()
    expect(await screen.findByText(/Cannot reach the API/)).toBeInTheDocument()
  })

  it('points users to Settings when the server wants an admin token', async () => {
    mockApi({ 'GET /api/projects': () => json({ error: { category: 'unauthorized', message: 'Missing or invalid admin token.' } }, 401) })
    renderApp('/app/projects')
    expect(await screen.findByText(/requires an admin token/i)).toBeInTheDocument()
  })

  it('checks off the getting-started steps from real data', async () => {
    mockApi({ 'GET /api/requests': { items: [], total: 4 }, 'GET /api/prompts': { items: [], total: 2 }, 'GET /api/datasets': { items: [], total: 0 },
      'GET /api/experiments': { items: [], total: 0 }, 'GET /api/deployments': [] })
    renderApp('/app')
    const item = await screen.findByText('Run a prompt in the Playground')
    expect(item.closest('li').querySelector('a')).toBeNull() // done: no "Go" link
    expect(screen.getByText('Upload a dataset').closest('li').querySelector('a')).not.toBeNull()
  })
})

/* ---------------- projects ---------------- */
describe('projects', () => {
  it('creates a project and deletes one after confirmation', async () => {
    const calls = mockApi({ 'POST /api/projects': (c) => ({ ...PROJECTS.items[0], id: 'p2', name: c.body.name }), 'DELETE /api/projects/p1': () => json(null, 204) })
    renderApp('/app/projects')
    await userEvent.click(await screen.findByRole('button', { name: /new project/i }))
    await userEvent.type(screen.getByLabelText('Name'), 'Docs Helper')
    await userEvent.click(screen.getByRole('button', { name: 'Create project' }))
    await waitFor(() => expect(last(calls, 'POST', '/api/projects').body.name).toBe('Docs Helper'))

    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(await screen.findByText(/cannot be deleted/i)).toBeInTheDocument()
    expect(last(calls, 'DELETE', '/api/projects/p1')).toBeUndefined() // nothing deleted before confirming
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(last(calls, 'DELETE', '/api/projects/p1')).toBeDefined())
  })

  it('invites the user to create a first project', async () => {
    mockApi({ 'GET /api/projects': { items: [], total: 0 } })
    renderApp('/app/projects')
    expect(await screen.findByText('No projects yet')).toBeInTheDocument()
  })
})

/* ---------------- playground ---------------- */
describe('playground', () => {
  async function open(routes = {}) {
    const calls = mockApi({ 'POST /api/generate': GEN, 'POST /api/feedback': { id: 'f1' }, 'GET /api/prompts': { items: [], total: 0 }, ...routes })
    renderApp('/app/playground')
    await screen.findByRole('heading', { name: 'Playground' })
    return calls
  }

  it('lets the user pick a provider and model, enter their own key, and run', async () => {
    const calls = await open()
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')
    expect(within(screen.getByLabelText('Model')).getAllByRole('option').map((o) => o.textContent)).toEqual(['GPT-4.1 mini', 'GPT-5', 'Custom model ID…'])
    await userEvent.type(screen.getByLabelText('OpenAI API key'), 'sk-mine-123')
    await userEvent.type(screen.getByLabelText('Prompt'), 'say hello')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByText('hello back')).toBeInTheDocument()
    const call = last(calls, 'POST', '/api/generate')
    expect(call.headers['X-Provider-Api-Key']).toBe('sk-mine-123')
    expect(call.body).toMatchObject({ prompt: 'say hello', provider: 'openai', model: 'gpt-4.1-mini' })
    expect(JSON.stringify(call.body)).not.toContain('sk-mine-123')
    expect(call.body).not.toHaveProperty('top_p')
    expect(screen.getByText('7')).toBeInTheDocument() // total tokens
  })

  it('has no Top-p control and disables temperature for fixed-temperature models', async () => {
    await open()
    expect(screen.queryByText(/top-?p/i)).toBeNull()
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')
    await userEvent.selectOptions(screen.getByLabelText('Model'), 'gpt-5')
    expect(screen.getByRole('slider')).toBeDisabled()
    expect(screen.getByText('Fixed temperature.')).toBeInTheDocument()
  })

  it('accepts any custom model ID', async () => {
    const calls = await open()
    await userEvent.selectOptions(screen.getByLabelText('Model'), '__custom__')
    await userEvent.type(screen.getByLabelText('Custom model ID'), 'brand-new-model')
    await userEvent.type(screen.getByLabelText('Prompt'), 'hi')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    await screen.findByText('hello back')
    expect(last(calls, 'POST', '/api/generate').body.model).toBe('brand-new-model')
  })

  it('disables Run until there is a prompt', async () => {
    await open()
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Prompt'), 'x')
    expect(screen.getByRole('button', { name: 'Run' })).toBeEnabled()
  })

  it('compares two setups side by side', async () => {
    const calls = await open()
    await userEvent.click(screen.getByLabelText(/Compare two setups/i))
    expect(screen.getAllByLabelText('Provider')).toHaveLength(2)
    await userEvent.type(screen.getByLabelText('Prompt'), 'compare me')
    await userEvent.click(screen.getByRole('button', { name: 'Run both' }))
    await waitFor(() => expect(all(calls, 'POST', '/api/generate')).toHaveLength(2))
    expect(await screen.findAllByText('hello back')).toHaveLength(2)
  })

  it('shows a plain-language error when the key is missing', async () => {
    await open({ 'POST /api/generate': () => json({ error: { category: 'missing_api_key', message: 'No API key for openai.' } }, 400) })
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')
    await userEvent.type(screen.getByLabelText('Prompt'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    expect(await screen.findByText('No API key for openai.')).toBeInTheDocument()
    expect(screen.getByText(/Add your model API key/)).toBeInTheDocument()
  })

  it('sends a star rating for the answer', async () => {
    const calls = await open()
    await userEvent.type(screen.getByLabelText('Prompt'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    await screen.findByText('hello back')
    await userEvent.click(screen.getByRole('radio', { name: '4 stars' }))
    await userEvent.type(screen.getByLabelText('Comment'), 'nice')
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(last(calls, 'POST', '/api/feedback').body).toEqual({ request_id: 'req1', rating: 4, comment: 'nice' }))
  })

  it('saves the prompt and its settings as a prompt version', async () => {
    const calls = await open({ 'POST /api/prompts': { prompt: { id: 'pr1' }, version: { version: 1 } } })
    await userEvent.click(screen.getByLabelText('Prompt'))
    await userEvent.paste('Summarise {{text}}') // typing braces would be read as key commands
    await userEvent.click(screen.getByRole('button', { name: 'Run' }))
    await screen.findByText('hello back')
    await userEvent.click(screen.getByRole('button', { name: /save as prompt/i }))
    await userEvent.type(await screen.findByLabelText('Prompt name'), 'Summariser')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(last(calls, 'POST', '/api/prompts')).toBeDefined())
    expect(last(calls, 'POST', '/api/prompts').body).toMatchObject({ project_id: 'p1', name: 'Summariser', template: 'Summarise {{text}}', provider: 'mock', model: 'mock-model' })
  })
})

/* ---------------- deployments ---------------- */
const SECRET = `llmops_0123456789ab_${'A'.repeat(43)}`
const DEP = { id: 'dep1', name: 'Greeter', status: 'active', project_id: 'p1', latest_version: 1, environments: { development: null, staging: null, production: 1 } }
const VER = { version: 1, prompt_id: 'pr1', prompt_name: 'greet', prompt_version: 1, status: 'ready', variables: ['name'], config: { provider: 'mock', model: 'mock-model' },
  health: { status: 'healthy', detail: 'all checks passed' }, created_at: '2026-10-12T10:00:00', validation_report: { passed: true, checks: [{ name: 'model_call', passed: true, detail: 'ok' }] } }
const depRoutes = (extra = {}) => ({
  'GET /api/deployments': [DEP], 'GET /api/deployments/dep1/versions': [VER], 'GET /api/deployments/dep1/usage': { empty: true }, 'GET /api/deployments/dep1/events': [],
  'GET /api/prompts': { items: [{ id: 'pr1', name: 'greet', latest_version: 1 }], total: 1 },
  'GET /api/prompts/pr1/versions': [{ version: 1, provider: 'mock', model: 'mock-model', variables: ['name'], evaluation_results: [] }],
  'GET /api/api-keys': [], ...extra,
})

describe('deployments', () => {
  it('shows live environments and a copy-paste call example without secrets', async () => {
    mockApi(depRoutes())
    renderApp('/app/deployments')
    expect(await screen.findByText('v1')).toBeInTheDocument()
    expect(screen.getAllByText('nothing live')).toHaveLength(2) // development and staging
    const code = (await screen.findByText(/\/v1\/deployments\/dep1\/invoke/)).textContent
    expect(code).toContain('<YOUR_API_KEY>')
    expect(code).not.toContain('llmops_0')
  })

  it('shows a new API key exactly once', async () => {
    const calls = mockApi(depRoutes({ 'POST /api/api-keys': { id: 'k1', name: 'mobile', prefix: 'llmops_0123456789ab', secret: SECRET } }))
    renderApp('/app/deployments')
    await userEvent.click(await screen.findByRole('tab', { name: 'API keys' }))
    await userEvent.type(screen.getByLabelText('Key name'), 'mobile')
    await userEvent.click(screen.getByRole('button', { name: 'Create API key' }))
    expect(await screen.findByText(SECRET)).toBeInTheDocument()
    expect(screen.getByText(/will NOT be shown again/)).toBeInTheDocument()
    expect(last(calls, 'POST', '/api/api-keys').body).toMatchObject({ project_id: 'p1', environments: ['production'] })
    await userEvent.click(screen.getByRole('button', { name: 'I have copied it' }))
    expect(screen.queryByText(SECRET)).toBeNull()
    await userEvent.click(screen.getByRole('tab', { name: 'Deployments' }))
    await userEvent.click(screen.getByRole('tab', { name: 'API keys' }))
    expect(screen.queryByText(SECRET)).toBeNull()
  })

  it('requires an explicit confirmation before promoting to production', async () => {
    const calls = mockApi(depRoutes({ 'POST /api/deployments/dep1/promote': DEP }))
    renderApp('/app/deployments')
    const promote = await screen.findByRole('button', { name: 'Promote' })
    expect(promote).toBeDisabled()
    await userEvent.click(screen.getByLabelText(/changes what live callers receive/i))
    await userEvent.click(promote)
    await waitFor(() => expect(last(calls, 'POST', '/api/deployments/dep1/promote').body).toEqual({ version: 1, environment: 'production' }))
  })

  it('sends sample inputs and validation options when publishing and reports failed checks', async () => {
    const failed = { ...VER, version: 2, status: 'failed', validation_report: { passed: false, checks: [{ name: 'json_output', passed: false, detail: 'not JSON' }] } }
    const calls = mockApi(depRoutes({ 'POST /api/deployments/dep1/versions': failed }))
    renderApp('/app/deployments')
    await screen.findByText('Publish a new version')
    await userEvent.click(screen.getByLabelText('Output must be valid JSON'))
    await userEvent.click(await screen.findByRole('button', { name: 'Validate and publish' }))
    await waitFor(() => expect(last(calls, 'POST', '/api/deployments/dep1/versions')).toBeDefined())
    expect(last(calls, 'POST', '/api/deployments/dep1/versions').body).toMatchObject({ prompt_id: 'pr1', prompt_version: 1, validation: { expect_json: true, sample_inputs: [] } })
    expect(await screen.findByText('not JSON')).toBeInTheDocument()
  })

  it('rejects malformed sample inputs before calling the server', async () => {
    const calls = mockApi(depRoutes())
    renderApp('/app/deployments')
    await screen.findByText('Publish a new version')
    await userEvent.type(screen.getByLabelText(/Sample inputs/), 'not json')
    expect(await screen.findByText(/JSON list of objects/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Validate and publish' })).toBeDisabled()
    expect(last(calls, 'POST', '/api/deployments/dep1/versions')).toBeUndefined()
  })

  it('tries the public endpoint with a bearer key and shows safe errors', async () => {
    const calls = mockApi(depRoutes({ 'POST /v1/deployments/dep1/invoke': () => json({ error: { category: 'rate_limited', message: 'Rate limit exceeded. Please slow down.' } }, 429, { 'Retry-After': '9' }) }))
    renderApp('/app/deployments')
    await userEvent.click(await screen.findByRole('tab', { name: 'Try it' }))
    await userEvent.type(await screen.findByLabelText('Input: name'), 'Ada')
    await userEvent.type(screen.getByLabelText('API key'), SECRET)
    await userEvent.click(screen.getByRole('button', { name: 'Call the endpoint' }))
    expect(await screen.findByText(/Retry after 9 seconds/)).toBeInTheDocument()
    const call = last(calls, 'POST', '/v1/deployments/dep1/invoke')
    expect(call.headers.Authorization).toBe(`Bearer ${SECRET}`)
    expect(call.body).toEqual({ inputs: { name: 'Ada' }, environment: 'production' })
    expect(document.body.textContent).not.toContain(SECRET)
  })
})

/* ---------------- monitoring ---------------- */
const SUMMARY = { empty: false, total: 10, success: 8, failed: 2, error_rate: 0.2,
  latency: { avg_ms: 450, p50_ms: 400, p95_ms: 800, p99_ms: 800, method: 'nearest-rank percentile' },
  tokens: { input: 80, output: 160, total: 240, requests_with_usage: 8, requests_without_usage: 2 },
  cost: { totals_by_currency: { USD: 0.09 }, by_model: [], complete: false, note: 'Estimate only.' }, feedback: { count: 0 }, input_length: { n: 10, mean: 50, min: 1, max: 99, p50: 50, p95: 90 } }
const monRoutes = (summary) => ({
  'GET /api/monitoring/summary': summary, 'GET /api/monitoring/timeseries': { granularity: 'day', note: 'gaps mean no traffic', points: [{ bucket: '2026-10-11', requests: 10, success: 8, failed: 2, avg_latency_ms: 450, input_tokens: 80, output_tokens: 160 }] },
  'GET /api/monitoring/breakdown': { models: [{ provider: 'openai', model: 'gpt-4.1-mini', requests: 10, error_rate: 0.2, avg_latency_ms: 450, input_tokens: 80, output_tokens: 160 }], prompt_versions: [] },
})

describe('monitoring', () => {
  it('shows an honest empty state instead of zeros', async () => {
    mockApi(monRoutes({ empty: true, total: 0 }))
    renderApp('/app/monitoring')
    expect(await screen.findByText('No requests in this range')).toBeInTheDocument()
    expect(screen.queryByText('Total requests')).toBeNull()
  })

  it('renders figures computed by the backend', async () => {
    mockApi(monRoutes(SUMMARY))
    renderApp('/app/monitoring')
    expect(await screen.findByText('Total requests')).toBeInTheDocument()
    expect(screen.getAllByText('20.0%').length).toBeGreaterThanOrEqual(1) // KPI and model table
    expect(screen.getAllByText('800 ms').length).toBeGreaterThanOrEqual(1) // p95 and p99
    expect(screen.getByText('0.0900 USD')).toBeInTheDocument()
    expect(screen.getByText(/2 request\(s\) have no token counts/)).toBeInTheDocument()
  })

  it('says cost is unavailable when no price is configured', async () => {
    mockApi(monRoutes({ ...SUMMARY, cost: { totals_by_currency: {}, by_model: [], complete: false, note: 'n' } }))
    renderApp('/app/monitoring')
    expect(await screen.findByText('unavailable')).toBeInTheDocument()
    expect(screen.getByText('no matching prices set')).toBeInTheDocument()
  })

  it('sends the selected filters and a valid date range to the backend', async () => {
    const calls = mockApi(monRoutes(SUMMARY))
    renderApp('/app/monitoring')
    await screen.findByText('Total requests')
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')
    await userEvent.selectOptions(screen.getByLabelText('Project'), 'p1')
    await waitFor(() => expect(last(calls, 'GET', '/api/monitoring/summary').query).toMatchObject({ provider: 'openai', project_id: 'p1' }))
    const q = last(calls, 'GET', '/api/monitoring/summary').query
    expect(new Date(q.start).getTime()).toBeLessThan(new Date(q.end).getTime())
  })

  it('lists alerts with their wording', async () => {
    mockApi({ ...monRoutes(SUMMARY), 'GET /api/monitoring/alerts': { note: 'live', alerts: [{ type: 'input_length_change', severity: 'info', title: 'Input length distribution changed', message: 'This is not proof of harmful data drift.' }] },
      'GET /api/monitoring/quality': { series: [], by_prompt_version: [], note: 'n' }, 'GET /api/monitoring/thresholds': { min_requests: 20, error_rate_max: 0.2, latency_p95_ms_max: null, quality_drop_max: 0.1, format_failure_rate_max: 0.2, feedback_avg_min: 3, input_length_change_max: 0.5, min_samples: 5 } })
    renderApp('/app/monitoring')
    await userEvent.click(await screen.findByRole('tab', { name: 'Quality and alerts' }))
    expect((await screen.findAllByText(/not proof of harmful data drift/)).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Input length distribution changed.', { exact: false })).toBeInTheDocument()
  })
})

/* ---------------- settings ---------------- */
describe('settings', () => {
  it('stores the admin token for this tab only and sends it on later requests', async () => {
    mockApi({ 'GET /api/monitoring/policy': { store_prompt_text: false, redaction_enabled: true, retention_days: 0, never_stored: ['API keys'], streaming_first_token_time: 'not captured', retries: 'not captured' } })
    renderApp('/app/settings')
    await userEvent.type(await screen.findByLabelText('Token'), 'admin-xyz')
    await userEvent.click(screen.getByRole('button', { name: 'Save token' }))
    expect(sessionStorage.getItem('llmops.admin')).toBe('admin-xyz')
    expect(localStorage.getItem('llmops.admin')).toBeNull()
    const calls = mockApi({ 'GET /api/projects': { items: [] } })
    await api.projects.list()
    expect(calls[0].headers['X-Admin-Token']).toBe('admin-xyz')
  })

  it('explains what happens to prompt data', async () => {
    mockApi({ 'GET /api/monitoring/policy': { store_prompt_text: false, redaction_enabled: true, retention_days: 30, never_stored: ['API keys', 'authorization headers'], streaming_first_token_time: 'not captured', retries: 'not captured' } })
    renderApp('/app/settings')
    expect(await screen.findByText('Not stored (default)')).toBeInTheDocument()
    expect(screen.getByText('30 days')).toBeInTheDocument()
  })
})

describe('routing', () => {
  it('sends unknown addresses to the landing page', async () => {
    mockApi()
    renderApp('/nowhere')
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/Ship LLM features/)
  })
  it('uses the catalog helper data consistently', () => { expect(CATALOG.providers.map((p) => p.id)).toContain('openai') })
})

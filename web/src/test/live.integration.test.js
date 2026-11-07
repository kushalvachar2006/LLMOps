// Runs only when LIVE_URL points at a running app (see docs/setup.md). Uses the REAL api module and no mocks.
import { describe, expect, it } from 'vitest'
import { api, ApiError } from '../lib/api'
import { setAdminToken } from '../lib/session'

describe.skipIf(!process.env.LIVE_URL)('live backend through the web proxy', () => {
  it('walks the whole product loop with the real client', async () => {
    const health = await api.health()
    expect(health.admin_auth).toBe(true)
    const blocked = await api.projects.list().catch((e) => e)
    expect(blocked).toBeInstanceOf(ApiError)
    expect(blocked.category).toBe('unauthorized')
    setAdminToken(process.env.LIVE_ADMIN_TOKEN)

    const catalog = await api.models()
    expect(catalog.providers.map((p) => p.id)).toContain('mock')
    const project = await api.projects.create({ name: `Live ${Date.now()}`, description: '' })
    const gen = await api.generate({ prompt: 'hello', provider: 'mock', model: 'mock-model', project_id: project.id })
    expect(gen.text).toContain('hello')
    await api.feedback.add({ request_id: gen.request_id, rating: 5, comment: 'mail me at a@b.com' })
    expect((await api.feedback.list({ project_id: project.id }))[0].comment).not.toContain('a@b.com')

    const prompt = await api.prompts.create({ project_id: project.id, name: 'greet', template: 'Say hi to {{name}}', provider: 'mock', model: 'mock-model' })
    const ds = await api.datasets.create({ project_id: project.id, name: 'names', filename: 'n.csv', content: 'name,answer\nAda,hi\nBo,hi\n', description: '' })
    const exp = await api.experiments.run({ project_id: project.id, name: 'e1', prompt_id: prompt.prompt.id, dataset_id: ds.dataset.id, reference_field: 'answer', evaluators: [{ type: 'text_similarity', params: {} }] })
    expect(exp.status).toBe('completed')
    expect(exp.summary.rows_run).toBe(2)

    const dep = await api.deployments.create({ project_id: project.id, name: 'Greeter', description: '' })
    const ver = await api.deployments.publish(dep.id, { prompt_id: prompt.prompt.id })
    expect(ver.status).toBe('ready')
    await api.deployments.promote(dep.id, 1, 'production')
    const key = await api.apiKeys.create({ project_id: project.id, name: 'live', environments: ['production'], rate_limit_per_minute: 3 })
    expect((await api.apiKeys.list(project.id))[0]).not.toHaveProperty('secret')

    const out = await api.invoke(dep.id, { name: 'Ada' }, 'production', key.secret)
    expect(out.output).toContain('Say hi to Ada')
    const bad = await api.invoke(dep.id, { name: 'Ada' }, 'production', 'llmops_000000000000_' + 'x'.repeat(43)).catch((e) => e)
    expect(bad.status).toBe(401)
    await api.invoke(dep.id, { name: 'a' }, 'production', key.secret)
    await api.invoke(dep.id, { name: 'b' }, 'production', key.secret)
    const limited = await api.invoke(dep.id, { name: 'c' }, 'production', key.secret).catch((e) => e)
    expect(limited.status).toBe(429)
    expect(limited.message).toMatch(/Retry after \d+ seconds/)
    await api.apiKeys.revoke((await api.apiKeys.list(project.id))[0].id)
    expect((await api.invoke(dep.id, { name: 'd' }, 'production', key.secret).catch((e) => e)).status).toBe(401)

    const usage = await api.deployments.usage(dep.id)
    expect(usage.total).toBe(3)
    const summary = await api.monitoring.summary({ project_id: project.id })
    expect(summary.empty).toBe(false)
    // 1 playground call + 2 experiment rows + 1 validation probe + 3 successful API calls.
    // The rejected 401 / 429 calls never reach a model, so they create no trace.
    expect(summary.total).toBe(7)
  }, 60000)
})

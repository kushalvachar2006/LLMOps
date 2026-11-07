import { useState } from 'react'
import { KeyRound, Rocket } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate, fmtInt, fmtMs, fmtPct } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { getProviderKey } from '../lib/session'
import { useModels } from '../lib/useModels'
import { useToast } from '../context/providers'
import {
  Async, Badge, Button, Card, CodeBlock, ConfirmButton, DataTable, EmptyState, ErrorNotice, Metric, Notice,
  PageHeader, ProjectGate, ProviderKeyField, SelectField, StatusBadge, Tabs, TextArea, TextField,
} from '../components/ui'

const ENVS = ['development', 'staging', 'production']

function Checks({ report }) {
  if (!report) return null
  return <DataTable rows={report.checks} rowKey={(c) => c.name} columns={[{ key: 'name', label: 'Check', render: (c) => <code>{c.name}</code> },
    { key: 'passed', label: 'Result', render: (c) => <Badge tone={c.passed ? 'success' : 'danger'}>{c.passed ? 'passed' : 'failed'}</Badge> }, { key: 'detail', label: 'Detail' }]} />
}

function Publish({ dep, project, onDone }) {
  const toast = useToast()
  const prompts = useAsync(() => api.prompts.list(project.id), [project.id])
  const models = useModels()
  const [pid, setPid] = useState(''); const [pver, setPver] = useState('')
  const [samples, setSamples] = useState(''); const [json, setJson] = useState(false); const [maxChars, setMaxChars] = useState(0); const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false); const [error, setError] = useState(null); const [report, setReport] = useState(null)
  const list = prompts.data?.items || []
  const prompt = list.find((p) => p.id === pid) || list[0]
  const ver = Number(pver) || prompt?.latest_version
  const versions = useAsync(() => api.prompts.versions(prompt.id), [prompt?.id], { enabled: !!prompt })
  const pv = versions.data?.find((v) => v.version === ver)
  const prov = models.data?.providers.find((p) => p.id === pv?.provider)
  let samplesError = ''; let parsed = []
  if (samples.trim()) { try { parsed = JSON.parse(samples); if (!Array.isArray(parsed) || !parsed.every((s) => s && typeof s === 'object' && !Array.isArray(s))) throw new Error() } catch { samplesError = 'Must be a JSON list of objects, for example [{"name": "Ada"}].' } }
  if (!prompts.loading && !list.length) return <Notice>Save a prompt first (Playground → “Save as prompt”).</Notice>
  async function publish() {
    setBusy(true); setError(null); setReport(null)
    try {
      const out = await api.deployments.publish(dep.id, { prompt_id: prompt.id, prompt_version: ver, change_description: note || null,
        validation: { sample_inputs: parsed, expect_json: json, max_output_chars: Number(maxChars) || null } }, getProviderKey(pv.provider) || undefined)
      setReport(out)
      out.status === 'ready' ? toast.success(`Version ${out.version} passed all checks and is ready to promote.`) : toast.error(`Version ${out.version} failed validation and cannot be promoted.`)
      onDone()
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  return (
    <Card title="Publish a new version"><div className="stack">
      <p className="small muted">Publishing runs validation checks, including a real model call. A version only becomes “ready” if every check passes. These calls use tokens.</p>
      <div className="grid grid-2"><SelectField label="Prompt" value={prompt?.id || ''} options={list.map((p) => ({ value: p.id, label: p.name }))} onChange={(e) => { setPid(e.target.value); setPver('') }} />
        <SelectField label="Prompt version" value={ver || ''} options={prompt ? Array.from({ length: prompt.latest_version }, (_, i) => prompt.latest_version - i) : []} onChange={(e) => setPver(e.target.value)} /></div>
      {pv && <p className="small muted">Model {pv.provider} / {pv.model} · the API will need inputs: {pv.variables.map((v) => <code key={v} style={{ marginRight: 6 }}>{v}</code>)}{!pv.variables.length && 'none'}</p>}
      <TextArea label="Sample inputs (optional JSON list)" mono value={samples} onChange={(e) => setSamples(e.target.value)} style={{ minHeight: 60 }} placeholder='[{"name": "Ada"}]' error={samplesError} hint="Used for the validation call. If empty, placeholder text is used." />
      <div className="grid grid-3"><label className="check"><input type="checkbox" checked={json} onChange={(e) => setJson(e.target.checked)} />Output must be valid JSON</label>
        <TextField label="Max output characters (0 = no limit)" type="number" min="0" value={maxChars} onChange={(e) => setMaxChars(e.target.value)} />
        <TextField label="Change description" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></div>
      {prov && prov.id !== 'mock' && <ProviderKeyField provider={prov.id} label={prov.label} serverKey={prov.server_key_configured} />}
      {error && <ErrorNotice error={error} />}
      <div><Button variant="primary" icon={Rocket} loading={busy} disabled={!pv || !!samplesError} onClick={publish}>Validate and publish</Button></div>
      {report && <Checks report={report.validation_report} />}
    </div></Card>
  )
}

function DeploymentsTab({ project }) {
  const toast = useToast()
  const list = useAsync(() => api.deployments.list(project.id), [project.id])
  const [pick, setPick] = useState(''); const [name, setName] = useState(''); const [creating, setCreating] = useState(false)
  const deps = list.data || []
  const dep = deps.find((d) => d.id === pick) || deps[0]
  const versions = useAsync(() => api.deployments.versions(dep.id), [dep?.id, dep?.latest_version], { enabled: !!dep })
  const usage = useAsync(() => api.deployments.usage(dep.id), [dep?.id], { enabled: !!dep })
  const events = useAsync(() => api.deployments.events(dep.id), [dep?.id, dep?.environments?.production, dep?.environments?.staging, dep?.environments?.development], { enabled: !!dep })
  const [promo, setPromo] = useState({ version: '', env: 'production', confirm: false })
  const [inspect, setInspect] = useState(null)
  const refresh = () => { list.reload(); versions.reload(); events.reload() }

  async function create() {
    setCreating(true)
    try { const d = await api.deployments.create({ project_id: project.id, name, description: '' }); toast.success(`Deployment "${d.name}" created.`); setName(''); setPick(d.id); list.reload() }
    catch (e) { toast.error(e.message) } finally { setCreating(false) }
  }
  async function act(fn, ok) { try { await fn(); toast.success(ok); refresh() } catch (e) { toast.error(e.message) } }

  return (
    <div className="stack-lg">
      <Card title="Create a deployment"><form className="row" onSubmit={(e) => { e.preventDefault(); create() }}>
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} className="grow" />
        <Button type="submit" variant="primary" loading={creating} disabled={!name.trim()} style={{ alignSelf: 'flex-end' }}>Create</Button></form></Card>
      {list.error && <ErrorNotice error={list.error} onRetry={list.reload} />}
      {!list.loading && !deps.length && <EmptyState icon={Rocket} title="No deployments yet">A deployment is a named endpoint other apps can call.</EmptyState>}
      {dep && (<>
        <SelectField label="Deployment" value={dep.id} options={deps.map((d) => ({ value: d.id, label: d.name }))} onChange={(e) => setPick(e.target.value)} />
        <div className="grid grid-3">{ENVS.map((e) => <Metric key={e} label={e} value={dep.environments[e] ? `v${dep.environments[e]}` : 'nothing live'} />)}</div>
        <p className="small faint">Deployment ID <code>{dep.id}</code> · <StatusBadge status={dep.status} /></p>
        <Publish dep={dep} project={project} onDone={refresh} />
        <Card title="Versions"><Async state={versions} empty={<p className="muted">No versions yet.</p>}>{(vs) => (<div className="stack">
          <DataTable rows={vs} rowKey={(v) => v.version} columns={[{ key: 'version', label: 'Version', render: (v) => <b>v{v.version}</b> },
            { key: 'prompt', label: 'Prompt', render: (v) => `${v.prompt_name} v${v.prompt_version}` }, { key: 'model', label: 'Model', render: (v) => `${v.config.provider} / ${v.config.model}` },
            { key: 'status', label: 'Status', render: (v) => <StatusBadge status={v.status} /> }, { key: 'health', label: 'Health', render: (v) => <StatusBadge status={v.health.status} /> },
            { key: 'created_at', label: 'Created', render: (v) => fmtDate(v.created_at) }]} />
          <div className="grid grid-3">
            <SelectField label="Promote version" value={promo.version || vs.find((v) => v.status === 'ready')?.version || ''} options={vs.filter((v) => v.status === 'ready').map((v) => v.version)} onChange={(e) => setPromo({ ...promo, version: e.target.value })} />
            <SelectField label="To environment" value={promo.env} options={ENVS} onChange={(e) => setPromo({ ...promo, env: e.target.value, confirm: false })} />
            <div className="stack-sm" style={{ justifyContent: 'flex-end' }}>
              {promo.env === 'production' && <label className="check"><input type="checkbox" checked={promo.confirm} onChange={(e) => setPromo({ ...promo, confirm: e.target.checked })} />This changes what live callers receive</label>}
              <Button variant="primary" disabled={!vs.some((v) => v.status === 'ready') || (promo.env === 'production' && !promo.confirm)}
                onClick={() => { const n = Number(promo.version || vs.find((v) => v.status === 'ready').version); act(() => api.deployments.promote(dep.id, n, promo.env), `v${n} is now live in ${promo.env}.`) }}>Promote</Button></div>
          </div>
          <p className="small faint">Promoting an older version later acts as a rollback.</p>
          <div className="row">{ENVS.filter((e) => dep.environments[e]).map((e) => <ConfirmButton key={e} label={`Take ${e} offline`} confirmText={`Callers using the ${e} environment will start receiving "no version is live".`} onConfirm={() => act(() => api.deployments.unpublish(dep.id, e), `${e} is offline.`)} />)}</div>
          <SelectField label="Inspect version" value={inspect ?? vs[0].version} options={vs.map((v) => v.version)} onChange={(e) => setInspect(Number(e.target.value))} />
          {(() => { const v = vs.find((x) => x.version === (inspect ?? vs[0].version)) || vs[0]; return (<div className="stack">
            <p className="small">Health: <StatusBadge status={v.health.status} /> <span className="muted">{v.health.detail}</span></p>
            <Checks report={v.validation_report} />
            <div><Button size="sm" onClick={() => act(() => api.deployments.healthCheck(dep.id, v.version, getProviderKey(v.config.provider) || undefined), 'Health check finished.')}>Run health check now</Button>
              <span className="small faint" style={{ marginLeft: 10 }}>Uses a live model call and your key for {v.config.provider}.</span></div></div>) })()}
        </div>)}</Async></Card>
        <CallExample dep={dep} versions={versions.data} />
        <Card title="Usage (last 7 days)"><Async state={usage}>{(u) => u.empty ? <p className="muted">No calls recorded yet.</p> : (<div className="stack">
          <div className="grid grid-4"><Metric label="Calls" value={fmtInt(u.total)} /><Metric label="Error rate" value={fmtPct(u.error_rate)} /><Metric label="Avg latency" value={fmtMs(u.avg_latency_ms)} /><Metric label="Tokens" value={fmtInt(u.input_tokens + u.output_tokens)} /></div>
          <DataTable rows={u.by_version} rowKey={(r) => String(r.version)} columns={[{ key: 'version', label: 'Version' }, { key: 'requests', label: 'Calls', num: true }, { key: 'failed', label: 'Failed', num: true }, { key: 'avg_latency_ms', label: 'Avg latency', num: true, render: (r) => fmtMs(r.avg_latency_ms) }]} />
          <p className="small faint">{u.note}</p></div>)}</Async></Card>
        <Card title="History"><Async state={events} empty={<p className="muted">Nothing yet.</p>}>{(ev) => <DataTable rows={ev} rowKey={(e) => e.id} columns={[{ key: 'at', label: 'When', render: (e) => fmtDate(e.at) }, { key: 'type', label: 'Action' }, { key: 'environment', label: 'Environment' }, { key: 'from_version', label: 'From' }, { key: 'to_version', label: 'To' }]} />}</Async></Card>
      </>)}
    </div>
  )
}

function CallExample({ dep, versions }) {
  const live = dep.environments.production || dep.environments.staging || dep.environments.development
  const v = versions?.find((x) => x.version === live)
  if (!v) return null
  const inputs = JSON.stringify(Object.fromEntries(v.variables.map((n) => [n, '...'])))
  return <Card title="How other apps call this"><div className="stack">
    <CodeBlock code={`curl -X POST ${window.location.origin}/v1/deployments/${dep.id}/invoke \\\n  -H "Authorization: Bearer <YOUR_API_KEY>" \\\n  -H "Content-Type: application/json" \\\n  -d '{"inputs": ${inputs}, "environment": "production"}'`} />
    <p className="small muted">Create a key on the API keys tab. Callers never see your prompt, model settings or any provider key.</p></div></Card>
}

function KeysTab({ project }) {
  const toast = useToast()
  const keys = useAsync(() => api.apiKeys.list(project.id), [project.id])
  const [name, setName] = useState(''); const [envs, setEnvs] = useState(['production']); const [limit, setLimit] = useState(60)
  const [fresh, setFresh] = useState(null); const [busy, setBusy] = useState(false)
  async function create() {
    setBusy(true)
    try { setFresh(await api.apiKeys.create({ project_id: project.id, name, environments: envs, rate_limit_per_minute: Number(limit) })); setName(''); keys.reload() }
    catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  return (
    <div className="stack-lg">
      <p className="muted small">Keys let other applications call this project's live deployments. A key only works for this project and the environments you choose.</p>
      {fresh && (<div className="secret-box stack-sm"><b>Key “{fresh.name}” created. Copy it now: it will NOT be shown again.</b>
        <CodeBlock code={fresh.secret} /><div><Button size="sm" onClick={() => setFresh(null)}>I have copied it</Button></div></div>)}
      <Card title="Create an API key"><form className="stack" onSubmit={(e) => { e.preventDefault(); create() }}>
        <div className="grid grid-3"><TextField label="Key name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. mobile app" maxLength={100} />
          <TextField label="Calls per minute" type="number" min="1" max="1000" value={limit} onChange={(e) => setLimit(e.target.value)} />
          <div className="field"><span className="label">Allowed environments</span><div className="row">{ENVS.map((e) => <label key={e} className="check"><input type="checkbox" checked={envs.includes(e)} onChange={(ev) => setEnvs(ev.target.checked ? [...envs, e] : envs.filter((x) => x !== e))} />{e}</label>)}</div></div></div>
        <div><Button type="submit" variant="primary" icon={KeyRound} loading={busy} disabled={!name.trim() || !envs.length}>Create API key</Button></div></form></Card>
      <Card title="Keys"><Async state={keys} empty={<p className="muted">No API keys yet for this project.</p>}>{(rows) => (
        <DataTable rows={rows} rowKey={(k) => k.id} columns={[{ key: 'name', label: 'Name' }, { key: 'prefix', label: 'Key', render: (k) => <code>{k.prefix}…</code> },
          { key: 'environments', label: 'Environments', render: (k) => k.environments.join(', ') }, { key: 'rate_limit_per_minute', label: 'Limit/min', num: true },
          { key: 'request_count', label: 'Calls', num: true }, { key: 'last_used_at', label: 'Last used', render: (k) => fmtDate(k.last_used_at) },
          { key: 'status', label: 'Status', render: (k) => <StatusBadge status={k.revoked_at ? 'revoked' : 'active'} /> },
          { key: 'act', label: '', render: (k) => !k.revoked_at && <ConfirmButton label="Revoke" confirmText={`Revoke "${k.name}"? Apps using it will stop working immediately.`}
            onConfirm={async () => { try { await api.apiKeys.revoke(k.id); toast.success('Key revoked.'); keys.reload() } catch (e) { toast.error(e.message) } }} /> }]} />)}</Async></Card>
    </div>
  )
}

function TryTab({ project }) {
  const list = useAsync(() => api.deployments.list(project.id), [project.id])
  const [pick, setPick] = useState(''); const [env, setEnv] = useState('production'); const [token, setToken] = useState(''); const [vals, setVals] = useState({})
  const [out, setOut] = useState(null); const [err, setErr] = useState(null); const [busy, setBusy] = useState(false)
  const deps = list.data || []; const dep = deps.find((d) => d.id === pick) || deps[0]
  const liveEnvs = dep ? ENVS.filter((e) => dep.environments[e]) : []
  const useEnv = liveEnvs.includes(env) ? env : liveEnvs[0]
  const versions = useAsync(() => api.deployments.versions(dep.id), [dep?.id], { enabled: !!dep })
  const v = versions.data?.find((x) => x.version === dep?.environments[useEnv])
  async function call() {
    setBusy(true); setErr(null); setOut(null)
    try { setOut(await api.invoke(dep.id, vals, useEnv, token.trim())) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  if (list.error) return <ErrorNotice error={list.error} />
  if (!dep) return <EmptyState title="No deployments yet" />
  if (!liveEnvs.length) return <Notice>Nothing is live yet. Publish and promote a version first.</Notice>
  return (
    <Card title="Call the public endpoint"><div className="stack">
      <p className="small muted">This sends a real request to <code>/v1/deployments/…/invoke</code> with your API key, exactly like an outside app would.</p>
      <div className="grid grid-2"><SelectField label="Deployment" value={dep.id} options={deps.map((d) => ({ value: d.id, label: d.name }))} onChange={(e) => setPick(e.target.value)} />
        <SelectField label="Environment" value={useEnv} options={liveEnvs} onChange={(e) => setEnv(e.target.value)} /></div>
      {v?.variables.map((n) => <TextField key={n} label={`Input: ${n}`} value={vals[n] || ''} onChange={(e) => setVals({ ...vals, [n]: e.target.value })} />)}
      <TextField label="API key" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} hint="Paste a key from the API keys tab. It is not stored." />
      {err && <ErrorNotice error={err} />}
      <div><Button variant="primary" loading={busy} disabled={!token.trim() || !v} onClick={call}>Call the endpoint</Button></div>
      {out && <div className="stack-sm"><div style={{ whiteSpace: 'pre-wrap' }}>{out.output || <em>empty output</em>}</div>
        <p className="small faint">Version {out.version} · {fmtMs(out.latency_ms)} · {fmtInt(out.usage.total_tokens)} tokens · request {out.request_id}</p></div>}
    </div></Card>
  )
}

export default function Deployments() {
  const [tab, setTab] = useState('deployments')
  return (
    <div className="stack-lg">
      <PageHeader title="Deployments" subtitle="Publish a validated prompt as a versioned endpoint that other apps can call." />
      <ProjectGate>{(project) => (<>
        <Tabs value={tab} onChange={setTab} tabs={[{ id: 'deployments', label: 'Deployments' }, { id: 'keys', label: 'API keys' }, { id: 'try', label: 'Try it' }]} />
        {tab === 'deployments' && <DeploymentsTab project={project} />}{tab === 'keys' && <KeysTab project={project} />}{tab === 'try' && <TryTab project={project} />}
      </>)}</ProjectGate>
    </div>
  )
}

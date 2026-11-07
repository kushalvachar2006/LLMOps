import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { GitCompareArrows, Play, Save } from 'lucide-react'
import { api } from '../lib/api'
import { fmtInt, fmtMs } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { getProviderKey } from '../lib/session'
import { modelInfo, useModels } from '../lib/useModels'
import { useProject, useToast } from '../context/providers'
import {
  Async, Button, Card, ErrorNotice, Metric, Modal, Notice, PageHeader, ProviderKeyField, SelectField,
  Stars, TextArea, TextField,
} from '../components/ui'

const CUSTOM = '__custom__'

function initialCfg(catalog) {
  const provider = catalog.default_provider
  const first = catalog.providers.find((p) => p.id === provider)?.models[0]?.id || CUSTOM
  return { provider, model: first, custom: '', temperature: 0.7, max: 1024, system: '' }
}
const modelId = (c) => (c.model === CUSTOM ? c.custom.trim() : c.model)

function ConfigForm({ cfg, setCfg, catalog, title }) {
  const tempId = useId()
  const prov = catalog.providers.find((p) => p.id === cfg.provider)
  const info = modelInfo(catalog, cfg.provider, cfg.model)
  const tempMax = info ? info.temp_max : cfg.provider === 'anthropic' ? 1 : 2
  const supportsTemp = info ? info.supports_temperature : true
  const set = (patch) => setCfg({ ...cfg, ...patch })
  return (
    <div className="stack">
      {title && <h3>{title}</h3>}
      <div className="grid grid-2">
        <SelectField label="Provider" value={cfg.provider}
          options={catalog.providers.map((p) => ({ value: p.id, label: p.label }))}
          onChange={(e) => { const p = catalog.providers.find((x) => x.id === e.target.value); set({ provider: p.id, model: p.models[0]?.id || CUSTOM, custom: '' }) }} />
        <SelectField label="Model" value={cfg.model}
          options={[...prov.models.map((m) => ({ value: m.id, label: m.label })), { value: CUSTOM, label: 'Custom model ID…' }]}
          onChange={(e) => set({ model: e.target.value, temperature: Math.min(cfg.temperature, modelInfo(catalog, cfg.provider, e.target.value)?.temp_max ?? tempMax) })} />
      </div>
      {cfg.model === CUSTOM && <TextField label="Custom model ID" value={cfg.custom} onChange={(e) => set({ custom: e.target.value })} placeholder="e.g. a newly released model" />}
      {info?.note && <p className="small faint">{info.note}</p>}
      <div className="grid grid-2">
        <div className="field"><label htmlFor={tempId}>Temperature: <b>{supportsTemp ? cfg.temperature.toFixed(2) : 'fixed'}</b></label>
          <input id={tempId} type="range" min="0" max={tempMax} step="0.05" value={Math.min(cfg.temperature, tempMax)} disabled={!supportsTemp}
            onChange={(e) => set({ temperature: Number(e.target.value) })} /></div>
        <TextField label="Max output tokens" type="number" min="1" max="8192" value={cfg.max} onChange={(e) => set({ max: Number(e.target.value) })} />
      </div>
      <TextArea label="System instruction (optional)" value={cfg.system} onChange={(e) => set({ system: e.target.value })} style={{ minHeight: 64 }} maxLength={5000} />
      {prov.id !== 'mock' && <ProviderKeyField provider={prov.id} label={prov.label} serverKey={prov.server_key_configured} />}
    </div>
  )
}

function Rate({ requestId }) {
  const toast = useToast()
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState('')
  const [sent, setSent] = useState(false)
  async function send() {
    try { await api.feedback.add({ request_id: requestId, rating, comment: comment || null }); setSent(true); toast.success('Thanks, feedback saved.') }
    catch (e) { toast.error(e.message) }
  }
  if (sent) return <p className="small muted">Feedback saved ({rating}/5).</p>
  return (
    <div className="stack-sm">
      <div className="row"><span className="small muted">Rate this answer</span><Stars value={rating} onChange={setRating} /></div>
      {rating > 0 && (
        <div className="row"><input className="input grow" aria-label="Comment" placeholder="Comment (optional)" maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
          <Button size="sm" onClick={send}>Send</Button></div>
      )}
    </div>
  )
}

function Result({ item, onSave }) {
  const { cfg, res, err } = item
  return (
    <Card title={<span>{cfg.provider} · {res?.model || modelId(cfg)}</span>}>
      {err ? <ErrorNotice error={err} /> : (
        <div className="stack">
          <div style={{ whiteSpace: 'pre-wrap' }}>{res.text || <em className="muted">The model returned no text.</em>}</div>
          <div className="grid grid-3">
            <Metric label="Latency" value={fmtMs(res.latency_ms)} />
            <Metric label="Tokens in / out" value={`${fmtInt(res.usage.input_tokens)} / ${fmtInt(res.usage.output_tokens)}`} />
            <Metric label="Total tokens" value={fmtInt(res.usage.total_tokens)} />
          </div>
          {!res.telemetry_recorded && <Notice tone="warning">The answer was generated, but saving its trace failed. See the backend logs.</Notice>}
          <p className="faint small">Request {res.request_id}</p>
          <Rate requestId={res.request_id} />
          {onSave && <div><Button icon={Save} size="sm" onClick={onSave}>Save as prompt</Button></div>}
        </div>
      )}
    </Card>
  )
}

function SavePrompt({ prompt, cfg, onClose }) {
  const { project } = useProject()
  const toast = useToast()
  const existing = useAsync(() => api.prompts.list(project.id), [project.id])
  const items = existing.data?.items || []
  const [mode, setMode] = useState('new')
  const [name, setName] = useState('')
  const [target, setTarget] = useState('')
  const [change, setChange] = useState('')
  const [busy, setBusy] = useState(false)
  async function save() {
    setBusy(true)
    const body = { template: prompt, provider: cfg.provider, model: modelId(cfg), temperature: cfg.temperature,
      max_output_tokens: cfg.max, system_instruction: cfg.system || null, change_description: change || null }
    try {
      if (mode === 'new') { await api.prompts.create({ ...body, project_id: project.id, name }); toast.success(`Saved "${name}" as version 1.`) }
      else { const v = await api.prompts.addVersion(target || items[0].id, body); toast.success(`Saved as version ${v.version}.`) }
      onClose()
    } catch (e) { toast.error(e.message); setBusy(false) }
  }
  return (
    <Modal title="Save as prompt" onClose={onClose}>
      <div className="stack">
        <p className="small muted">Saves the prompt text and this configuration as an immutable version in <b>{project.name}</b>. Use <code>{'{{field}}'}</code> placeholders to run it over datasets.</p>
        <SelectField label="Save as" value={mode} onChange={(e) => setMode(e.target.value)}
          options={[{ value: 'new', label: 'A new prompt' }, ...(items.length ? [{ value: 'existing', label: 'A new version of an existing prompt' }] : [])]} />
        {mode === 'new' ? <TextField label="Prompt name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} autoFocus />
          : <SelectField label="Prompt" value={target || items[0]?.id} onChange={(e) => setTarget(e.target.value)} options={items.map((p) => ({ value: p.id, label: p.name }))} />}
        <TextField label="Change description (optional)" value={change} onChange={(e) => setChange(e.target.value)} maxLength={500} />
        <div className="row" style={{ justifyContent: 'flex-end' }}><Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={busy} disabled={mode === 'new' && !name.trim()} onClick={save}>Save</Button></div>
      </div>
    </Modal>
  )
}

function PlaygroundInner({ catalog }) {
  const [a, setA] = useState(() => initialCfg(catalog))
  const [b, setB] = useState(() => initialCfg(catalog))
  const [compare, setCompare] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [results, setResults] = useState(null)
  const [running, setRunning] = useState(false)
  const [saving, setSaving] = useState(false)
  const active = compare ? [a, b] : [a]
  const ready = prompt.trim() && active.every((c) => modelId(c))

  async function run() {
    setRunning(true)
    const settled = await Promise.allSettled(active.map((cfg) => api.generate({
      prompt, provider: cfg.provider, model: modelId(cfg), temperature: cfg.temperature,
      max_output_tokens: cfg.max, system_instruction: cfg.system || null,
    }, getProviderKey(cfg.provider) || undefined)))
    setResults({ prompt, items: settled.map((s, i) => ({ cfg: active[i], res: s.value, err: s.reason })) })
    setRunning(false)
  }
  return (
    <div className="stack-lg">
      <PageHeader title="Playground" subtitle="Try a prompt on any model. Bring your own API key, or use the mock provider offline."
        actions={<label className="check"><input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} /><GitCompareArrows size={16} /> Compare two setups</label>} />
      <div className={compare ? 'grid grid-2' : ''}>
        <Card><ConfigForm cfg={a} setCfg={setA} catalog={catalog} title={compare ? 'Setup A' : 'Model'} /></Card>
        {compare && <Card><ConfigForm cfg={b} setCfg={setB} catalog={catalog} title="Setup B" /></Card>}
      </div>
      <Card>
        <TextArea label="Prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} maxLength={20000} style={{ minHeight: 150 }}
          placeholder="Write your prompt. Use {{field}} placeholders if you plan to run it over a dataset."
          hint={`${prompt.length.toLocaleString()} / 20,000 characters`} />
        <div className="row" style={{ marginTop: 14 }}>
          <Button variant="primary" icon={Play} loading={running} disabled={!ready} onClick={run}>Run{compare ? ' both' : ''}</Button>
          <span className="small faint">Each run is saved as a trace you can see in <Link to="/app/monitoring">Monitoring</Link>.</span>
        </div>
      </Card>
      {results && (
        <div className={results.items.length > 1 ? 'grid grid-2' : ''}>
          {results.items.map((it, i) => <Result key={i} item={it} onSave={!it.err && i === 0 ? () => setSaving(true) : null} />)}
        </div>
      )}
      {saving && results && <SavePrompt prompt={results.prompt} cfg={results.items[0].cfg} onClose={() => setSaving(false)} />}
    </div>
  )
}

export default function Playground() {
  const state = useModels()
  return <Async state={state}>{(catalog) => <PlaygroundInner catalog={catalog} />}</Async>
}

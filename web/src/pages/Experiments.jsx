import { useState } from 'react'
import { FlaskConical } from 'lucide-react'
import { api } from '../lib/api'
import { fmtInt, fmtMs, fmtPct, fmtScore, fmtDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { getProviderKey } from '../lib/session'
import { useModels } from '../lib/useModels'
import { useToast } from '../context/providers'
import {
  Async, Badge, Button, Card, DataTable, EmptyState, ErrorNotice, Metric, Notice, PageHeader, ProjectGate,
  ProviderKeyField, SelectField, StatusBadge, Tabs, TextArea, TextField,
} from '../components/ui'

const kindLabel = (k) => (k === 'objective' ? 'objective' : 'model judgment')

function Summary({ exp }) {
  const s = exp.summary
  const metrics = Object.entries(s.metrics || {})
  return (
    <div className="stack">
      <div className="row"><h3>{exp.name}</h3><StatusBadge status={exp.status} />
        <span className="small faint">prompt v{exp.prompt_version} · dataset v{exp.dataset_version} ({exp.split}) · {exp.config.provider}/{exp.config.model} · temp {exp.config.temperature}</span></div>
      <div className="grid grid-4">
        <Metric label="Rows run" value={`${s.rows_run} / ${s.rows_planned}`} /><Metric label="Failed" value={s.failed} />
        <Metric label="Avg latency" value={fmtMs(s.avg_latency_ms)} /><Metric label="Tokens" value={fmtInt(s.total_tokens)} />
      </div>
      {exp.abort_reason && <Notice tone="warning">The run stopped early ({exp.abort_reason}). The remaining rows were not sent.</Notice>}
      {metrics.length > 0 && (
        <DataTable rows={metrics.map(([name, m]) => ({ name, ...m }))} rowKey={(m) => m.name}
          columns={[{ key: 'name', label: 'Metric', render: (m) => <code>{m.name}</code> }, { key: 'kind', label: 'Kind', render: (m) => <Badge tone={m.kind === 'objective' ? 'success' : 'warning'}>{kindLabel(m.kind)}</Badge> },
            { key: 'mean_score', label: 'Mean score', num: true, render: (m) => fmtScore(m.mean_score) }, { key: 'pass_rate', label: 'Pass rate', num: true, render: (m) => fmtPct(m.pass_rate, 0) },
            { key: 'n_scored', label: 'Scored', num: true }, { key: 'n_unscored', label: 'Unscored', num: true }]} />
      )}
      {metrics.some(([, m]) => m.kind !== 'objective') && <p className="small muted">Model-judgment scores are opinions from another model, not measurements.</p>}
    </div>
  )
}

function Rows({ expId }) {
  const state = useAsync(() => api.experiments.results(expId), [expId])
  return (
    <Async state={state}>
      {(r) => (
        <DataTable rows={r.items} rowKey={(x) => x.row_index} columns={[
          { key: 'row_index', label: '#', num: true },
          { key: 'input', label: 'Input', clip: true, render: (x) => JSON.stringify(x.input) },
          { key: 'output', label: 'Output', clip: true, render: (x) => x.output ?? <em>{x.error_category}</em> },
          { key: 'status', label: 'Status', render: (x) => <StatusBadge status={x.status} /> },
          { key: 'latency_ms', label: 'Latency', num: true, render: (x) => fmtMs(x.latency_ms) },
          { key: 'evaluations', label: 'Scores', render: (x) => x.evaluations.map((e) => `${e.name}: ${fmtScore(e.score)}`).join(' · ') }]} />
      )}
    </Async>
  )
}

function EvaluatorParams({ type, params, setParams }) {
  const set = (p) => setParams({ ...params, ...p })
  if (type === 'exact_match') return <label className="check"><input type="checkbox" checked={!!params.case_sensitive} onChange={(e) => set({ case_sensitive: e.target.checked })} />Case sensitive</label>
  if (type === 'text_similarity') return <TextField label="Pass threshold (0–1)" type="number" min="0" max="1" step="0.05" value={params.threshold ?? 0.8} onChange={(e) => set({ threshold: Number(e.target.value) })} />
  if (type === 'contains_keywords') return (
    <div className="grid grid-2"><TextField label="Keywords (comma separated)" value={params._kw || ''} onChange={(e) => set({ _kw: e.target.value, keywords: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
      <SelectField label="Match" value={params.mode || 'all'} options={['all', 'any']} onChange={(e) => set({ mode: e.target.value })} /></div>)
  if (type === 'max_length') return <TextField label="Max characters" type="number" min="1" value={params.max_chars ?? 500} onChange={(e) => set({ max_chars: Number(e.target.value) })} />
  if (type === 'llm_judge') return (<div className="stack-sm"><TextArea label="Rubric: what makes a good answer?" value={params.rubric || ''} onChange={(e) => set({ rubric: e.target.value })} style={{ minHeight: 70 }} />
    <TextField label="Pass score (1–5)" type="number" min="1" max="5" value={params.pass_score ?? 4} onChange={(e) => set({ pass_score: Number(e.target.value) })} />
    <Notice tone="warning">The judge makes extra model calls (extra cost) and gives an opinion, not a measurement.</Notice></div>)
  if (type === 'json_valid') return <TextArea label="JSON Schema (optional)" mono value={params._schema || ''} style={{ minHeight: 70 }} onChange={(e) => {
    let schema; try { schema = e.target.value.trim() ? JSON.parse(e.target.value) : undefined } catch { schema = undefined }
    set({ _schema: e.target.value, schema })
  }} />
  return null
}
const cleanParams = (p) => Object.fromEntries(Object.entries(p).filter(([k, v]) => !k.startsWith('_') && v !== undefined))

function RunForm({ project }) {
  const toast = useToast()
  const prompts = useAsync(() => api.prompts.list(project.id), [project.id])
  const datasets = useAsync(() => api.datasets.list(project.id), [project.id])
  const evals = useAsync(() => api.evaluators(), [])
  const models = useModels()
  const [pid, setPid] = useState(''); const [pver, setPver] = useState('')
  const [did, setDid] = useState(''); const [dver, setDver] = useState('')
  const [split, setSplit] = useState('all'); const [maxRows, setMaxRows] = useState(10); const [ref, setRef] = useState('')
  const [name, setName] = useState(''); const [chosen, setChosen] = useState({})
  const [busy, setBusy] = useState(false); const [error, setError] = useState(null); const [result, setResult] = useState(null)

  const pList = prompts.data?.items || []; const dList = datasets.data?.items || []
  const prompt = pList.find((p) => p.id === pid) || pList[0]; const dataset = dList.find((d) => d.id === did) || dList[0]
  const pv = prompt ? Number(pver) || prompt.latest_version : null; const dv = dataset ? Number(dver) || dataset.latest_version : null
  const pVers = useAsync(() => api.prompts.versions(prompt.id), [prompt?.id], { enabled: !!prompt })
  const dVers = useAsync(() => api.datasets.versions(dataset.id), [dataset?.id], { enabled: !!dataset })
  const promptVersion = pVers.data?.find((v) => v.version === pv)
  const datasetVersion = dVers.data?.find((v) => v.version === dv)

  if (prompts.error || datasets.error) return <ErrorNotice error={prompts.error || datasets.error} />
  if (!prompts.loading && (!pList.length || !dList.length)) {
    return <EmptyState icon={FlaskConical} title="You need a prompt and a dataset first">Save a prompt from the Playground and upload a dataset, then come back here to run them together.</EmptyState>
  }
  const fields = datasetVersion?.schema.map((f) => f.name) || []
  const missing = (promptVersion?.variables || []).filter((v) => !fields.includes(v))
  const provider = models.data?.providers.find((p) => p.id === promptVersion?.provider)
  const picked = Object.keys(chosen).filter((k) => chosen[k])

  async function run() {
    setBusy(true); setError(null); setResult(null)
    try {
      const exp = await api.experiments.run({
        project_id: project.id, name: name.trim() || `${prompt.name} v${pv}`, prompt_id: prompt.id, prompt_version: pv,
        dataset_id: dataset.id, dataset_version: dv, split, max_rows: Number(maxRows), reference_field: ref || null,
        evaluators: picked.map((t) => ({ type: t, params: cleanParams(chosen[t] === true ? {} : chosen[t]) })),
      }, getProviderKey(promptVersion.provider) || undefined)
      setResult(exp); toast.success(`Experiment finished: ${exp.status}.`)
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  return (
    <div className="stack-lg">
      <Card title="1. Choose what to test"><div className="stack">
        <div className="grid grid-4">
          <SelectField label="Prompt" value={prompt?.id || ''} options={pList.map((p) => ({ value: p.id, label: p.name }))} onChange={(e) => { setPid(e.target.value); setPver('') }} />
          <SelectField label="Prompt version" value={pv || ''} options={prompt ? Array.from({ length: prompt.latest_version }, (_, i) => prompt.latest_version - i) : []} onChange={(e) => setPver(e.target.value)} />
          <SelectField label="Dataset" value={dataset?.id || ''} options={dList.map((d) => ({ value: d.id, label: d.name }))} onChange={(e) => { setDid(e.target.value); setDver('') }} />
          <SelectField label="Dataset version" value={dv || ''} options={dataset ? Array.from({ length: dataset.latest_version }, (_, i) => dataset.latest_version - i) : []} onChange={(e) => setDver(e.target.value)} />
        </div>
        {promptVersion && <p className="small muted">Model: <b>{promptVersion.provider} / {promptVersion.model}</b> · the prompt uses {promptVersion.variables.map((v) => <code key={v} style={{ marginRight: 6 }}>{v}</code>)}</p>}
        {missing.length > 0 && <Notice tone="warning">This prompt uses field(s) the dataset does not have: {missing.join(', ')}.</Notice>}
        <div className="grid grid-3">
          <SelectField label="Rows to use" value={split} options={['all', ...Object.keys(datasetVersion?.split_counts || {})]} onChange={(e) => setSplit(e.target.value)} />
          <TextField label="Max rows" type="number" min="1" max="500" value={maxRows} onChange={(e) => setMaxRows(e.target.value)} hint="Each row is one model call and may cost money. The server also caps this." />
          <SelectField label="Reference answer column" value={ref} options={[{ value: '', label: '(none)' }, ...fields]} onChange={(e) => setRef(e.target.value)} />
        </div>
      </div></Card>
      <Card title="2. Choose how to score it"><Async state={evals}>{(list) => (
        <div className="stack">{list.map((e) => (
          <div key={e.type} className="card-flat stack-sm">
            <label className="check"><input type="checkbox" checked={!!chosen[e.type]} onChange={(ev) => setChosen({ ...chosen, [e.type]: ev.target.checked ? {} : false })} />
              <code>{e.type}</code> <Badge tone={e.kind === 'objective' ? 'success' : 'warning'}>{kindLabel(e.kind)}</Badge>{e.needs_reference && <span className="small faint">needs reference column</span>}</label>
            <p className="small muted">{e.description} <em>Limit: {e.limitations}</em></p>
            {chosen[e.type] && <EvaluatorParams type={e.type} params={chosen[e.type]} setParams={(p) => setChosen({ ...chosen, [e.type]: p })} />}
          </div>))}
        </div>)}</Async></Card>
      <Card title="3. Run"><div className="stack">
        <TextField label="Experiment name" value={name} onChange={(e) => setName(e.target.value)} placeholder={prompt ? `${prompt.name} v${pv}` : ''} maxLength={100} />
        {provider && provider.id !== 'mock' && <ProviderKeyField provider={provider.id} label={provider.label} serverKey={provider.server_key_configured} />}
        {error && <ErrorNotice error={error} />}
        <div><Button variant="primary" icon={FlaskConical} loading={busy} disabled={!promptVersion || !datasetVersion || missing.length > 0} onClick={run}>Run experiment</Button>
          {busy && <span className="small muted" style={{ marginLeft: 12 }}>Each row is a model call, so this can take a while…</span>}</div>
      </div></Card>
      {result && <Card title="Result"><div className="stack"><Summary exp={result} /><Rows expId={result.id} /></div></Card>}
    </div>
  )
}

function History({ project }) {
  const state = useAsync(() => api.experiments.list(project.id), [project.id])
  const [pick, setPick] = useState('')
  return (
    <Async state={state} empty={<EmptyState title="No experiments yet" />}>
      {(d) => {
        const e = d.items.find((x) => x.id === pick) || d.items[0]
        return (<div className="stack">
          <SelectField label="Experiment" value={e.id} options={d.items.map((x) => ({ value: x.id, label: `${x.name} · ${fmtDate(x.created_at).slice(0, 16)}` }))} onChange={(ev) => setPick(ev.target.value)} />
          <Summary exp={e} /><Rows expId={e.id} />
        </div>)
      }}
    </Async>
  )
}

function Compare({ project }) {
  const list = useAsync(() => api.experiments.list(project.id), [project.id])
  const [ids, setIds] = useState([])
  const cmp = useAsync(() => api.experiments.compare(ids), [ids.join(",")], { enabled: ids.length >= 2 })
  const items = list.data?.items || []
  const toggle = (id) => setIds((l) => (l.includes(id) ? l.filter((x) => x !== id) : l.length < 4 ? [...l, id] : l))
  return (
    <div className="stack">
      <p className="muted small">Pick 2 to 4 experiments.</p>
      <div className="stack-sm">{items.map((e) => <label key={e.id} className="check"><input type="checkbox" checked={ids.includes(e.id)} onChange={() => toggle(e.id)} />{e.name} <span className="faint small">· {fmtDate(e.created_at).slice(0, 16)}</span></label>)}</div>
      {!items.length && !list.loading && <p className="muted">No experiments yet.</p>}
      {ids.length >= 2 && (
        <Async state={cmp}>{(c) => (<>
          <DataTable rows={c.experiments} rowKey={(e) => e.id} columns={[{ key: 'name', label: 'Experiment' }, { key: 'status', label: 'Status', render: (e) => <StatusBadge status={e.status} /> },
            { key: 'lat', label: 'Avg latency', num: true, render: (e) => fmtMs(e.summary.avg_latency_ms) }, { key: 'tok', label: 'Tokens', num: true, render: (e) => fmtInt(e.summary.total_tokens) },
            ...[...new Set(c.experiments.flatMap((e) => Object.keys(e.summary.metrics || {})))].map((m) => ({ key: m, label: `${m} (mean)`, num: true, render: (e) => fmtScore(e.summary.metrics?.[m]?.mean_score) }))]} />
          {Object.keys(c.config_differences).length > 0 && <Card title="What differs between these runs"><DataTable rows={Object.entries(c.config_differences).map(([k, v]) => ({ k, v }))} rowKey={(r) => r.k}
            columns={[{ key: 'k', label: 'Setting' }, ...c.experiments.map((e, i) => ({ key: e.id, label: e.name, clip: true, render: (r) => String(r.v[i] ?? '') }))]} /></Card>}
          {c.aligned ? c.rows.map((r) => (
            <Card key={r.row_index} title={`Row ${r.row_index}`}><p className="small muted clip" style={{ maxWidth: '100%' }}>{JSON.stringify(r.input)}</p>
              <div className={`grid grid-${Math.min(c.experiments.length, 3) === 2 ? 2 : 3}`} style={{ marginTop: 10 }}>{c.experiments.map((e) => { const o = r.outputs[e.id]; return (
                <div key={e.id} className="card-flat"><b className="small">{e.name}</b><p style={{ whiteSpace: 'pre-wrap', margin: '6px 0' }}>{o?.output ?? <em>{o?.error_category}</em>}</p>
                  {o?.evaluations.map((ev) => <div key={ev.name} className="small faint">{ev.name}: {fmtScore(ev.score)}</div>)}</div>) })}</div></Card>
          )) : <Notice>These runs used different dataset versions or splits, so rows cannot be lined up. Only summary metrics are compared.</Notice>}
        </>)}</Async>)}
    </div>
  )
}

export default function Experiments() {
  const [tab, setTab] = useState('run')
  return (
    <div className="stack-lg">
      <PageHeader title="Experiments" subtitle="Run a prompt version over a dataset version and score every answer." />
      <ProjectGate>{(project) => (<>
        <Tabs value={tab} onChange={setTab} tabs={[{ id: 'run', label: 'Run' }, { id: 'history', label: 'History' }, { id: 'compare', label: 'Compare' }]} />
        {tab === 'run' && <RunForm project={project} />}{tab === 'history' && <History project={project} />}{tab === 'compare' && <Compare project={project} />}
      </>)}</ProjectGate>
    </div>
  )
}

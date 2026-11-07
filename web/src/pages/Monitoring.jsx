import { useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate, fmtInt, fmtMs, fmtPct, fmtScore, isoRange } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useModels } from '../lib/useModels'
import { useProject, useToast } from '../context/providers'
import { BarSeries, LineSeries } from '../components/charts'
import {
  Async, Badge, Button, Card, ConfirmButton, DataTable, EmptyState, ErrorNotice, Metric, Notice, PageHeader,
  SelectField, StatusBadge, Stars, Tabs, TextField,
} from '../components/ui'

const today = () => new Date().toISOString().slice(0, 10)

function Dashboard({ f }) {
  const summary = useAsync(() => api.monitoring.summary(f), [JSON.stringify(f)])  
  const series = useAsync(() => api.monitoring.timeseries(f), [JSON.stringify(f)])  
  const breakdown = useAsync(() => api.monitoring.breakdown(f), [JSON.stringify(f)])  
  return (
    <Async state={summary}>
      {(s) => s.empty ? (
        <EmptyState title="No requests in this range">Run something in the Playground or an experiment, or widen the date range. Nothing is shown rather than showing made-up numbers.</EmptyState>
      ) : (
        <div className="stack-lg">
          <div className="grid grid-4"><Metric label="Total requests" value={fmtInt(s.total)} /><Metric label="Succeeded" value={fmtInt(s.success)} />
            <Metric label="Failed" value={fmtInt(s.failed)} /><Metric label="Error rate" value={fmtPct(s.error_rate)} /></div>
          <div className="grid grid-4"><Metric label="Avg latency" value={fmtMs(s.latency.avg_ms)} /><Metric label="p50 latency" value={fmtMs(s.latency.p50_ms)} />
            <Metric label="p95 latency" value={fmtMs(s.latency.p95_ms)} /><Metric label="p99 latency" value={fmtMs(s.latency.p99_ms)} /></div>
          <p className="small faint">Latency percentiles: {s.latency.method}. Failed requests without a measured latency are excluded.</p>
          <div className="grid grid-3"><Metric label="Input tokens" value={fmtInt(s.tokens.input)} /><Metric label="Output tokens" value={fmtInt(s.tokens.output)} />
            <Metric label="Estimated cost" value={Object.keys(s.cost.totals_by_currency).length ? Object.entries(s.cost.totals_by_currency).map(([c, v]) => `${v.toFixed(4)} ${c}`).join(', ') : 'unavailable'}
              hint={Object.keys(s.cost.totals_by_currency).length ? 'estimate' : 'no matching prices set'} /></div>
          {s.tokens.requests_without_usage > 0 && <p className="small faint">{s.tokens.requests_without_usage} request(s) have no token counts (failed calls or providers that did not report usage) and are left out of token and cost totals.</p>}
          <Async state={series}>{(ts) => (<>
            <Card title="Requests over time"><BarSeries data={ts.points} xKey="bucket" stacked series={[{ key: 'success', color: 'var(--accent)' }, { key: 'failed', color: 'var(--danger)' }]} />
              <p className="small faint">Grouped by {ts.granularity}. {ts.note}</p></Card>
            <div className="grid grid-2"><Card title="Average latency (ms)"><LineSeries data={ts.points} xKey="bucket" series={[{ key: 'avg_latency_ms', label: 'avg latency', color: 'var(--accent-2)' }]} /></Card>
              <Card title="Tokens"><BarSeries data={ts.points} xKey="bucket" series={[{ key: 'input_tokens', color: 'var(--info)' }, { key: 'output_tokens', color: 'var(--warning)' }]} /></Card></div>
          </>)}</Async>
          <Async state={breakdown}>{(b) => (<>
            <Card title="Model comparison"><DataTable rows={b.models} rowKey={(r) => `${r.provider}${r.model}`} columns={[{ key: 'model', label: 'Model', render: (r) => `${r.provider} / ${r.model}` },
              { key: 'requests', label: 'Requests', num: true }, { key: 'error_rate', label: 'Error rate', num: true, render: (r) => fmtPct(r.error_rate) },
              { key: 'avg_latency_ms', label: 'Avg latency', num: true, render: (r) => fmtMs(r.avg_latency_ms) }, { key: 'input_tokens', label: 'In tokens', num: true, render: (r) => fmtInt(r.input_tokens) },
              { key: 'output_tokens', label: 'Out tokens', num: true, render: (r) => fmtInt(r.output_tokens) }]} /></Card>
            <Card title="Prompt-version comparison"><DataTable rows={b.prompt_versions} rowKey={(r) => `${r.prompt_id}${r.prompt_version}`} empty="No requests with a prompt version in this range (they come from experiments and deployments)."
              columns={[{ key: 'prompt', label: 'Prompt', render: (r) => `${r.prompt} v${r.prompt_version}` }, { key: 'requests', label: 'Requests', num: true },
                { key: 'error_rate', label: 'Error rate', num: true, render: (r) => fmtPct(r.error_rate) }, { key: 'avg_latency_ms', label: 'Avg latency', num: true, render: (r) => fmtMs(r.avg_latency_ms) },
                { key: 'avg_rating', label: 'Avg rating', num: true, render: (r) => r.avg_rating ?? 'n/a' }]} /></Card>
          </>)}</Async>
          {s.input_length?.n > 0 && <Card title="Input length (characters)"><DataTable rows={[s.input_length]} rowKey={() => 'il'} columns={['n', 'mean', 'min', 'p50', 'p95', 'max'].map((k) => ({ key: k, label: k, num: true, render: (r) => (r[k] == null ? 'n/a' : Number(r[k]).toLocaleString(undefined, { maximumFractionDigits: 0 })) }))} /></Card>}
        </div>
      )}
    </Async>
  )
}

function Quality({ f }) {
  const toast = useToast()
  const alerts = useAsync(() => api.monitoring.alerts(f), [JSON.stringify(f)])  
  const quality = useAsync(() => api.monitoring.quality(f), [JSON.stringify(f)])  
  const th = useAsync(() => api.monitoring.thresholds(), [])
  const [edit, setEdit] = useState(null)
  const t = edit || th.data
  const set = (p) => setEdit({ ...t, ...p })
  async function save() {
    try { await api.monitoring.saveThresholds({ ...t, latency_p95_ms_max: t.latency_p95_ms_max || null, feedback_avg_min: t.feedback_avg_min || null }); toast.success('Thresholds saved.'); setEdit(null); th.reload(); alerts.reload() }
    catch (e) { toast.error(e.message) }
  }
  return (
    <div className="stack-lg">
      <Card title="Alerts"><Async state={alerts}>{(a) => (<div className="stack">
        {!a.alerts.length && <Notice tone="success">No thresholds were exceeded in this range.</Notice>}
        {a.alerts.map((x, i) => <Notice key={i} tone={x.severity === 'warning' ? 'warning' : 'info'}><b>{x.title}.</b> {x.message}</Notice>)}
        <p className="small faint">{a.note}</p></div>)}</Async></Card>
      <Card title="Quality trend (from experiment evaluations)"><Async state={quality}>{(q) => {
        if (!q.series.length) return <p className="muted">No evaluation scores in this range. Run an experiment with metrics selected.</p>
        const buckets = [...new Set(q.series.map((r) => r.bucket))]
        const names = [...new Set(q.series.map((r) => `${r.metric} (${r.kind === 'objective' ? 'objective' : 'judgment'})`))]
        const data = buckets.map((b) => Object.fromEntries([['bucket', b], ...q.series.filter((r) => r.bucket === b).map((r) => [`${r.metric} (${r.kind === 'objective' ? 'objective' : 'judgment'})`, r.mean_score])]))
        return (<div className="stack"><LineSeries data={data} xKey="bucket" series={names.map((n) => ({ key: n }))} />
          <p className="small faint">{q.note} Judge scores use a 1–5 scale; other metrics use 0–1.</p>
          <DataTable rows={q.by_prompt_version} rowKey={(r) => `${r.prompt_id}${r.prompt_version}${r.metric}`} columns={[{ key: 'prompt', label: 'Prompt', render: (r) => `${r.prompt} v${r.prompt_version}` },
            { key: 'metric', label: 'Metric' }, { key: 'kind', label: 'Kind', render: (r) => <Badge tone={r.kind === 'objective' ? 'success' : 'warning'}>{r.kind === 'objective' ? 'objective' : 'judgment'}</Badge> },
            { key: 'mean_score', label: 'Mean', num: true, render: (r) => fmtScore(r.mean_score) }, { key: 'n_scored', label: 'Scored', num: true }]} /></div>)
      }}</Async></Card>
      <Card title="Alert thresholds"><Async state={th}>{() => t && (<div className="stack">
        <div className="grid grid-3"><TextField label="Min requests before rate alerts" type="number" min="1" value={t.min_requests} onChange={(e) => set({ min_requests: Number(e.target.value) })} />
          <TextField label="Max error rate (0–1)" type="number" step="0.01" min="0" max="1" value={t.error_rate_max} onChange={(e) => set({ error_rate_max: Number(e.target.value) })} />
          <TextField label="p95 latency limit (ms, blank = off)" type="number" min="1" value={t.latency_p95_ms_max ?? ''} onChange={(e) => set({ latency_p95_ms_max: e.target.value ? Number(e.target.value) : null })} /></div>
        <div className="grid grid-3"><TextField label="Max quality drop (0–1)" type="number" step="0.01" min="0" max="1" value={t.quality_drop_max} onChange={(e) => set({ quality_drop_max: Number(e.target.value) })} />
          <TextField label="Max format-failure rate (0–1)" type="number" step="0.01" min="0" max="1" value={t.format_failure_rate_max} onChange={(e) => set({ format_failure_rate_max: Number(e.target.value) })} />
          <TextField label="Min scored samples" type="number" min="1" value={t.min_samples} onChange={(e) => set({ min_samples: Number(e.target.value) })} /></div>
        <div className="grid grid-3"><TextField label="Min average rating (1–5, blank = off)" type="number" step="0.1" min="1" max="5" value={t.feedback_avg_min ?? ''} onChange={(e) => set({ feedback_avg_min: e.target.value ? Number(e.target.value) : null })} />
          <TextField label="Input length change (relative)" type="number" step="0.05" min="0" value={t.input_length_change_max} onChange={(e) => set({ input_length_change_max: Number(e.target.value) })} /></div>
        <div><Button variant="primary" disabled={!edit} onClick={save}>Save thresholds</Button></div>
        <p className="small faint">A change in input statistics is a signal to look closer, not proof of harmful data drift. Back quality concerns with evaluation scores or user feedback.</p></div>)}</Async></Card>
    </div>
  )
}

function Cost({ f }) {
  const toast = useToast()
  const models = useModels()
  const summary = useAsync(() => api.monitoring.summary(f), [JSON.stringify(f)])  
  const prices = useAsync(() => api.pricing.list(), [])
  const [form, setForm] = useState({ provider: 'openai', model: '', effective_from: today(), input_price: 0, output_price: 0, currency: 'USD', unit: 'per_1M_tokens', source_note: '' })
  const set = (p) => setForm({ ...form, ...p })
  async function add() {
    try { await api.pricing.add({ ...form, model: form.model.trim(), input_price: Number(form.input_price), output_price: Number(form.output_price), source_note: form.source_note || null })
      toast.success('Price added.'); prices.reload(); summary.reload() } catch (e) { toast.error(e.message) }
  }
  const label = { estimated: 'estimated', partial: 'partly priced', no_pricing: 'no price set', no_usage_data: 'no token counts', mixed_currency: 'mixed currencies' }
  return (
    <div className="stack-lg">
      <Card title="Estimated cost"><Async state={summary}>{(s) => s.empty ? <p className="muted">No requests in this range.</p> : (<div className="stack">
        <div className="row">{Object.entries(s.cost.totals_by_currency).map(([c, v]) => <Metric key={c} label={`Total (${c})`} value={v.toFixed(4)} />)}
          <Badge>estimate</Badge><Badge tone={s.cost.complete ? 'success' : 'warning'}>{s.cost.complete ? 'complete' : 'incomplete: some requests unpriced'}</Badge></div>
        <DataTable rows={s.cost.by_model} rowKey={(r) => `${r.provider}${r.model}`} columns={[{ key: 'model', label: 'Model', render: (r) => `${r.provider} / ${r.model}` }, { key: 'requests', label: 'Requests', num: true },
          { key: 'input_tokens', label: 'In tokens', num: true, render: (r) => fmtInt(r.input_tokens) }, { key: 'output_tokens', label: 'Out tokens', num: true, render: (r) => fmtInt(r.output_tokens) },
          { key: 'cost', label: 'Cost', num: true, render: (r) => (r.cost == null ? 'n/a' : `${r.cost.toFixed(4)} ${r.currency}`) },
          { key: 'status', label: 'Status', render: (r) => <Badge tone={r.status === 'estimated' ? 'success' : 'warning'}>{label[r.status] || r.status}</Badge> }]} />
        <p className="small faint">{s.cost.note}</p></div>)}</Async></Card>
      <Card title="Pricing configuration"><div className="stack">
        <Notice tone="warning">No prices are built in, because vendor prices change. Enter the price from your provider's own pricing page and note where you found it.</Notice>
        <div className="grid grid-3"><SelectField label="Provider" value={form.provider} options={(models.data?.providers || [{ id: 'openai' }]).map((p) => p.id)} onChange={(e) => set({ provider: e.target.value })} />
          <TextField label="Model ID (exact)" value={form.model} onChange={(e) => set({ model: e.target.value })} hint="Must match the model ID used in requests." />
          <TextField label="Effective from" type="date" value={form.effective_from} onChange={(e) => set({ effective_from: e.target.value })} /></div>
        <div className="grid grid-4"><TextField label="Input price" type="number" min="0" step="any" value={form.input_price} onChange={(e) => set({ input_price: e.target.value })} />
          <TextField label="Output price" type="number" min="0" step="any" value={form.output_price} onChange={(e) => set({ output_price: e.target.value })} />
          <TextField label="Currency" maxLength={3} value={form.currency} onChange={(e) => set({ currency: e.target.value.toUpperCase() })} />
          <SelectField label="Unit" value={form.unit} options={['per_1M_tokens', 'per_1K_tokens']} onChange={(e) => set({ unit: e.target.value })} /></div>
        <TextField label="Source note (optional)" value={form.source_note} onChange={(e) => set({ source_note: e.target.value })} maxLength={300} placeholder="e.g. provider pricing page, checked on 2026-10-11" />
        <div><Button variant="primary" disabled={!form.model.trim()} onClick={add}>Add price</Button></div>
        <Async state={prices} empty={<p className="muted">No prices configured yet.</p>}>{(rows) => (
          <DataTable rows={rows} rowKey={(p) => p.id} columns={[{ key: 'm', label: 'Model', render: (p) => `${p.provider} / ${p.model}` }, { key: 'effective_from', label: 'From' },
            { key: 'price', label: 'In / out', render: (p) => `${p.input_price} / ${p.output_price} ${p.currency} ${p.unit.replace(/_/g, ' ')}` }, { key: 'source_note', label: 'Source', clip: true },
            { key: 'x', label: '', render: (p) => <ConfirmButton label="Delete" confirmText="Delete this price? Costs for past requests will be recalculated without it." onConfirm={async () => { await api.pricing.remove(p.id); prices.reload(); summary.reload() }} /> }]} />)}</Async>
      </div></Card>
    </div>
  )
}

function Traces({ f, projectId }) {
  const toast = useToast()
  const reqs = useAsync(() => api.requests({ limit: 30, project_id: projectId }), [projectId])
  const fbs = useAsync(() => api.feedback.list({ ...f, limit: 20 }), [JSON.stringify(f)])  
  const [pick, setPick] = useState(''); const [rating, setRating] = useState(0); const [comment, setComment] = useState('')
  const items = reqs.data?.items || []
  const target = items.find((r) => r.request_id === pick) || items[0]
  async function send() {
    try { await api.feedback.add({ request_id: target.request_id, rating, comment: comment || null }); toast.success('Feedback saved.'); setRating(0); setComment(''); fbs.reload() }
    catch (e) { toast.error(e.message) }
  }
  return (
    <div className="stack-lg">
      <Card title="Recent request traces"><Async state={reqs} empty={<p className="muted">No traces yet.</p>}>{() => (<div className="stack">
        <DataTable rows={items} rowKey={(r) => r.request_id} columns={[{ key: 'created_at', label: 'Time', render: (r) => fmtDate(r.created_at) }, { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
          { key: 'model', label: 'Model', render: (r) => `${r.provider} / ${r.model}` }, { key: 'prompt_version', label: 'Prompt v', num: true }, { key: 'latency_ms', label: 'Latency', num: true, render: (r) => fmtMs(r.latency_ms) },
          { key: 'tokens', label: 'In / out', num: true, render: (r) => `${fmtInt(r.input_tokens)} / ${fmtInt(r.output_tokens)}` }, { key: 'retry_count', label: 'Retries', num: true }, { key: 'error_category', label: 'Error' }]} />
        <p className="small faint">Traces never contain API keys or authorization headers. Prompt and response text is not stored unless the server enables it (and is masked when it is).</p>
        <h4>Rate a request</h4>
        <SelectField label="Request" value={target?.request_id || ''} options={items.map((r) => ({ value: r.request_id, label: `${fmtDate(r.created_at)} · ${r.model} · ${r.status} · ${r.request_id.slice(0, 8)}` }))} onChange={(e) => setPick(e.target.value)} />
        <div className="row"><Stars value={rating} onChange={setRating} /><input className="input grow" aria-label="Comment" placeholder="Comment (optional)" value={comment} maxLength={1000} onChange={(e) => setComment(e.target.value)} />
          <Button disabled={!rating} onClick={send}>Send feedback</Button></div></div>)}</Async></Card>
      <Card title="Recent feedback"><Async state={fbs} empty={<p className="muted">No feedback in this range.</p>}>{(rows) => (
        <DataTable rows={rows} rowKey={(r) => r.id} columns={[{ key: 'created_at', label: 'Time', render: (r) => fmtDate(r.created_at) }, { key: 'rating', label: 'Rating', num: true }, { key: 'comment', label: 'Comment', clip: true },
          { key: 'model', label: 'Model' }, { key: 'prompt_version', label: 'Prompt v', num: true }]} />)}</Async></Card>
    </div>
  )
}

export default function Monitoring() {
  const { projects, project } = useProject()
  const models = useModels()
  const [scope, setScope] = useState('all')
  const [preset, setPreset] = useState('7d')
  const [custom, setCustom] = useState({ start: today(), end: today() })
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [stamp, setStamp] = useState(0)
  const [tab, setTab] = useState('dashboard')
  const range = useMemo(() => isoRange(preset, custom), [preset, custom, stamp]) // eslint-disable-line react-hooks/exhaustive-deps
  const projectId = scope === 'all' ? undefined : scope === 'current' ? project?.id : scope
  const f = { project_id: projectId, start: range.start, end: range.end, provider: provider || undefined, model: model.trim() || undefined }
  return (
    <div className="stack-lg">
      <PageHeader title="Monitoring" subtitle="Every number is computed from saved request, evaluation and feedback records."
        actions={<Button icon={RefreshCw} onClick={() => setStamp((s) => s + 1)}>Refresh</Button>} />
      <Card><div className="grid grid-4">
        <SelectField label="Project" value={scope} options={[{ value: 'all', label: 'All projects' }, ...projects.map((p) => ({ value: p.id, label: p.name }))]} onChange={(e) => setScope(e.target.value)} />
        <SelectField label="Date range" value={preset} options={[{ value: '24h', label: 'Last 24 hours' }, { value: '7d', label: 'Last 7 days' }, { value: '30d', label: 'Last 30 days' }, { value: 'custom', label: 'Custom' }]} onChange={(e) => setPreset(e.target.value)} />
        <SelectField label="Provider" value={provider} options={[{ value: '', label: 'All providers' }, ...(models.data?.providers || []).map((p) => ({ value: p.id, label: p.label }))]} onChange={(e) => setProvider(e.target.value)} />
        <TextField label="Model (optional)" value={model} onChange={(e) => setModel(e.target.value)} />
      </div>
        {preset === 'custom' && <div className="grid grid-2" style={{ marginTop: 12 }}><TextField label="From (UTC)" type="date" value={custom.start} onChange={(e) => setCustom({ ...custom, start: e.target.value })} />
          <TextField label="To (UTC)" type="date" value={custom.end} onChange={(e) => setCustom({ ...custom, end: e.target.value })} /></div>}</Card>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: 'dashboard', label: 'Dashboard' }, { id: 'quality', label: 'Quality and alerts' }, { id: 'cost', label: 'Cost and pricing' }, { id: 'traces', label: 'Feedback and traces' }]} />
      {tab === 'dashboard' && <Dashboard f={f} />}{tab === 'quality' && <Quality f={f} />}{tab === 'cost' && <Cost f={f} />}{tab === 'traces' && <Traces f={f} projectId={projectId} />}
    </div>
  )
}

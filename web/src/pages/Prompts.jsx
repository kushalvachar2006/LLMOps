import { useState } from 'react'
import { Undo2 } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate, fmtScore } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useModels } from '../lib/useModels'
import { useToast } from '../context/providers'
import {
  Async, Badge, Button, Card, CodeBlock, DataTable, EmptyState, ErrorNotice, Notice, PageHeader, ProjectGate,
  SelectField, Tabs, TextArea, TextField,
} from '../components/ui'

function Diff({ lines }) {
  if (!lines?.length) return <p className="muted small">No change.</p>
  return <pre className="code-block" style={{ margin: 0, padding: 12, overflowX: 'auto', fontSize: '.84rem' }}>
    {lines.map((l, i) => <span key={i} className={l.startsWith('+') && !l.startsWith('+++') ? 'diff-add' : l.startsWith('-') && !l.startsWith('---') ? 'diff-del' : ''}>{l || ' '}{'\n'}</span>)}</pre>
}

function Compare({ prompt, versions }) {
  const nums = versions.map((v) => v.version)
  const [a, setA] = useState(nums[nums.length - 1])
  const [b, setB] = useState(nums[0])
  const cmp = useAsync(() => api.prompts.compare(prompt.id, a, b), [prompt.id, a, b], { enabled: a !== b })
  if (nums.length < 2) return <p className="muted">Save at least two versions to compare them.</p>
  const opts = nums.map((n) => ({ value: n, label: `Version ${n}` }))
  return (
    <div className="stack">
      <div className="grid grid-2"><SelectField label="From" value={a} options={opts} onChange={(e) => setA(Number(e.target.value))} />
        <SelectField label="To" value={b} options={opts} onChange={(e) => setB(Number(e.target.value))} /></div>
      {a === b ? <Notice>Choose two different versions.</Notice> : (
        <Async state={cmp}>
          {(c) => (<>
            <DataTable rows={Object.entries(c.changes).map(([field, v]) => ({ field, ...v }))} rowKey={(r) => r.field}
              columns={[{ key: 'field', label: 'Setting' }, { key: 'a', label: `v${a}`, clip: true, render: (r) => String(r.a ?? '') },
                { key: 'b', label: `v${b}`, clip: true, render: (r) => String(r.b ?? '') },
                { key: 'changed', label: '', render: (r) => r.changed && <Badge tone="warning">changed</Badge> }]} />
            <h4>Template diff</h4><Diff lines={c.diffs.template} />
            <h4>System instruction diff</h4><Diff lines={c.diffs.system_instruction} />
          </>)}
        </Async>
      )}
    </div>
  )
}

function NewVersion({ prompt, latest, onSaved }) {
  const toast = useToast()
  const models = useModels()
  const [f, setF] = useState({ template: latest.template, system: latest.system_instruction || '', provider: latest.provider,
    model: latest.model, temperature: latest.temperature, max: latest.max_output_tokens, change: '' })
  const [busy, setBusy] = useState(false)
  const set = (p) => setF({ ...f, ...p })
  async function save() {
    setBusy(true)
    try {
      const v = await api.prompts.addVersion(prompt.id, { template: f.template, system_instruction: f.system || null, provider: f.provider,
        model: f.model, temperature: Number(f.temperature), max_output_tokens: Number(f.max), change_description: f.change || null })
      toast.success(`Saved version ${v.version}.`); onSaved()
    } catch (e) { toast.error(e.message) } finally { setBusy(false) }
  }
  const providers = (models.data?.providers || []).map((p) => ({ value: p.id, label: p.label }))
  return (
    <div className="stack">
      <p className="muted small">Starts from the latest version. Saving creates a new version; older ones are untouched.</p>
      <TextArea label="Prompt template" value={f.template} onChange={(e) => set({ template: e.target.value })} style={{ minHeight: 130 }} mono />
      <TextArea label="System instruction" value={f.system} onChange={(e) => set({ system: e.target.value })} style={{ minHeight: 60 }} />
      <div className="grid grid-4">
        <SelectField label="Provider" value={f.provider} options={providers.length ? providers : [f.provider]} onChange={(e) => set({ provider: e.target.value })} />
        <TextField label="Model ID" value={f.model} onChange={(e) => set({ model: e.target.value })} />
        <TextField label="Temperature" type="number" step="0.05" min="0" max="2" value={f.temperature} onChange={(e) => set({ temperature: e.target.value })} />
        <TextField label="Max tokens" type="number" min="1" max="8192" value={f.max} onChange={(e) => set({ max: e.target.value })} />
      </div>
      <TextField label="Change description" value={f.change} onChange={(e) => set({ change: e.target.value })} maxLength={500} />
      <div><Button variant="primary" loading={busy} disabled={!f.template.trim() || !f.model.trim()} onClick={save}>Save new version</Button></div>
    </div>
  )
}

function Registry({ project }) {
  const toast = useToast()
  const list = useAsync(() => api.prompts.list(project.id), [project.id])
  const [pick, setPick] = useState('')
  const prompts = list.data?.items || []
  const prompt = prompts.find((p) => p.id === pick) || prompts[0]
  const versions = useAsync(() => api.prompts.versions(prompt.id), [prompt?.id, prompt?.latest_version], { enabled: !!prompt })
  const [tab, setTab] = useState('view')
  const [sel, setSel] = useState(null)
  if (list.error) return <ErrorNotice error={list.error} onRetry={list.reload} />
  if (!list.loading && !prompts.length) {
    return <EmptyState title="No prompts yet">Run a prompt in the Playground and choose “Save as prompt” to create your first version.</EmptyState>
  }
  async function restore(n) {
    try { const v = await api.prompts.restore(prompt.id, n); toast.success(`Created version ${v.version} from version ${n}.`); list.reload(); versions.reload() }
    catch (e) { toast.error(e.message) }
  }
  return (
    <div className="stack-lg">
      <SelectField label="Prompt" value={prompt?.id || ''} options={prompts.map((p) => ({ value: p.id, label: `${p.name}  (v${p.latest_version})` }))} onChange={(e) => { setPick(e.target.value); setSel(null) }} />
      <Async state={versions}>
        {(vs) => {
          const current = vs.find((v) => v.version === (sel ?? vs[0].version)) || vs[0]
          return (<>
            <Card title={`${vs.length} version${vs.length > 1 ? 's' : ''}`}>
              <DataTable rows={vs} rowKey={(v) => v.version}
                columns={[{ key: 'version', label: 'Version', render: (v) => <b>v{v.version}</b> },
                  { key: 'created_at', label: 'Saved', render: (v) => fmtDate(v.created_at) },
                  { key: 'model', label: 'Model', render: (v) => `${v.provider} / ${v.model}` },
                  { key: 'temperature', label: 'Temp' },
                  { key: 'change_description', label: 'Note', clip: true },
                  { key: 'evaluation_results', label: 'Experiments', num: true, render: (v) => v.evaluation_results.length }]} />
            </Card>
            <Tabs value={tab} onChange={setTab} tabs={[{ id: 'view', label: 'View and restore' }, { id: 'compare', label: 'Compare' }, { id: 'new', label: 'New version' }]} />
            {tab === 'view' && (
              <div className="stack">
                <SelectField label="Version" value={current.version} options={vs.map((v) => ({ value: v.version, label: `Version ${v.version}` }))} onChange={(e) => setSel(Number(e.target.value))} />
                <CodeBlock code={current.template} />
                {current.system_instruction && <><h4>System instruction</h4><CodeBlock code={current.system_instruction} /></>}
                <p className="small muted">Fields: {current.variables.map((v) => <code key={v} style={{ marginRight: 6 }}>{`{{${v}}}`}</code>)}{!current.variables.length && 'none'}</p>
                {current.evaluation_results.length > 0 && (
                  <Card title="Evaluation results from experiments"><DataTable rows={current.evaluation_results} rowKey={(e) => e.experiment_id}
                    columns={[{ key: 'name', label: 'Experiment' }, { key: 'status', label: 'Status' },
                      { key: 'metrics', label: 'Metrics', render: (e) => Object.entries(e.metrics).map(([k, m]) => `${k}: ${fmtScore(m.mean_score)}`).join(' · ') }]} /></Card>
                )}
                <div><Button icon={Undo2} onClick={() => restore(current.version)}>Restore v{current.version} as a new version</Button></div>
              </div>
            )}
            {tab === 'compare' && <Compare prompt={prompt} versions={vs} />}
            {tab === 'new' && <NewVersion prompt={prompt} latest={vs[0]} onSaved={() => { list.reload(); versions.reload(); setTab('view') }} />}
          </>)
        }}
      </Async>
    </div>
  )
}

export default function Prompts() {
  return (<div className="stack-lg"><PageHeader title="Prompts" subtitle="Every save is a new numbered version. Old versions are never changed." />
    <ProjectGate>{(project) => <Registry project={project} />}</ProjectGate></div>)
}

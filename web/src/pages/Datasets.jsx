import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useToast } from '../context/providers'
import {
  Async, Button, Card, DataTable, EmptyState, ErrorNotice, Notice, PageHeader, ProjectGate, SelectField, TextField,
} from '../components/ui'

function UploadCard({ project, datasets, onDone }) {
  const toast = useToast()
  const input = useRef(null)
  const [over, setOver] = useState(false)
  const [file, setFile] = useState(null)
  const [target, setTarget] = useState('new')
  const [name, setName] = useState('')
  const [required, setRequired] = useState('')
  const [split, setSplit] = useState('none')
  const [ratios, setRatios] = useState({ train: 0.7, validation: 0.15, eval: 0.15 })
  const [seed, setSeed] = useState(42)
  const [change, setChange] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const pick = (f) => { setFile(f || null); setError(null) }
  async function upload() {
    setBusy(true); setError(null)
    let content
    try { content = await file.text() } catch { setError({ message: 'That file could not be read.' }); setBusy(false); return }
    const body = { filename: file.name, content, change_description: change || null, split_seed: Number(seed),
      required_fields: required.split(',').map((s) => s.trim()).filter(Boolean),
      split_ratios: split === 'random' ? ratios : null }
    try {
      if (target === 'new') {
        const out = await api.datasets.create({ ...body, project_id: project.id, name, description: '' })
        toast.success(`Dataset "${name}" created with ${out.version.row_count} rows.`)
      } else {
        const v = await api.datasets.addVersion(target, body)
        toast.success(`Saved version ${v.version} (${v.row_count} rows).`)
      }
      setFile(null); setName(''); onDone()
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const sum = Object.values(ratios).reduce((a, b) => a + Number(b), 0)
  const bad = split === 'random' && Math.abs(sum - 1) > 1e-6
  return (
    <Card title="Upload a dataset">
      <div className="stack">
        <div className={`drop ${over ? 'over' : ''}`} role="button" tabIndex={0}
          onClick={() => input.current.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]) }}>
          <Upload size={22} /><div>{file ? <b>{file.name} · {(file.size / 1024).toFixed(1)} KB</b> : 'Drop a .csv or .jsonl file here, or click to choose'}</div>
          <div className="small faint">Up to about 2 MB · UTF-8 text · first CSV row is the header</div>
          <input ref={input} type="file" accept=".csv,.jsonl,.ndjson" hidden onChange={(e) => pick(e.target.files[0])} />
        </div>
        <div className="grid grid-2">
          <SelectField label="Upload as" value={target} onChange={(e) => setTarget(e.target.value)}
            options={[{ value: 'new', label: 'A new dataset' }, ...datasets.map((d) => ({ value: d.id, label: `New version of "${d.name}"` }))]} />
          {target === 'new' && <TextField label="Dataset name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />}
        </div>
        <TextField label="Required fields (optional)" value={required} onChange={(e) => setRequired(e.target.value)} placeholder="question, answer" hint="Comma-separated. Every row must have a non-empty value in each." />
        <div className="grid grid-2">
          <SelectField label="Train / validation / eval split" value={split} onChange={(e) => setSplit(e.target.value)}
            options={[{ value: 'none', label: 'No split' }, { value: 'random', label: 'Random split by ratio' }]} hint={'Or add a "split" column (train, validation, eval) to your file.'} />
          <TextField label="Change description (optional)" value={change} onChange={(e) => setChange(e.target.value)} maxLength={500} />
        </div>
        {split === 'random' && (
          <div className="grid grid-4">
            {Object.keys(ratios).map((k) => <TextField key={k} label={k} type="number" min="0" max="1" step="0.05" value={ratios[k]} onChange={(e) => setRatios({ ...ratios, [k]: e.target.value })} />)}
            <TextField label="Seed" type="number" value={seed} onChange={(e) => setSeed(e.target.value)} hint="Same seed, same split" />
          </div>
        )}
        {bad && <Notice tone="warning">The ratios must add up to 1 (now {sum.toFixed(2)}).</Notice>}
        {error && <ErrorNotice error={error} />}
        <div><Button variant="primary" icon={Upload} loading={busy} disabled={!file || bad || (target === 'new' && !name.trim())} onClick={upload}>Upload</Button></div>
      </div>
    </Card>
  )
}

function Inspect({ dataset }) {
  const versions = useAsync(() => api.datasets.versions(dataset.id), [dataset.id, dataset.latest_version])
  const [sel, setSel] = useState(null)
  const [split, setSplit] = useState('all')
  return (
    <Async state={versions}>
      {(vs) => {
        const v = vs.find((x) => x.version === (sel ?? vs[0].version)) || vs[0]
        return (
          <div className="stack">
            <DataTable rows={vs} rowKey={(x) => x.version} columns={[
              { key: 'version', label: 'Version', render: (x) => <b>v{x.version}</b> }, { key: 'filename', label: 'File' },
              { key: 'row_count', label: 'Rows', num: true },
              { key: 'split_counts', label: 'Splits', render: (x) => Object.entries(x.split_counts).map(([k, n]) => `${k}: ${n}`).join(', ') },
              { key: 'created_at', label: 'Saved', render: (x) => fmtDate(x.created_at) }, { key: 'change_description', label: 'Note', clip: true }]} />
            <div className="grid grid-2">
              <SelectField label="Inspect version" value={v.version} options={vs.map((x) => ({ value: x.version, label: `Version ${x.version}` }))} onChange={(e) => { setSel(Number(e.target.value)); setSplit('all') }} />
              <SelectField label="Preview split" value={split} options={['all', ...Object.keys(v.split_counts)]} onChange={(e) => setSplit(e.target.value)} />
            </div>
            <h4>Schema</h4>
            <DataTable rows={v.schema} rowKey={(f) => f.name} columns={[{ key: 'name', label: 'Field', render: (f) => <code>{f.name}</code> }, { key: 'type', label: 'Type' },
              { key: 'empty_count', label: 'Empty', num: true }, { key: 'example', label: 'Example', clip: true }]} />
            <p className="small faint">Fingerprint (SHA-256): <code>{v.content_sha256.slice(0, 16)}…</code> proves exactly which file contents a result used.</p>
            <Preview dataset={dataset} version={v.version} split={split} fields={v.schema.map((f) => f.name)} />
          </div>
        )
      }}
    </Async>
  )
}

function Preview({ dataset, version, split, fields }) {
  const rows = useAsync(() => api.datasets.rows(dataset.id, version, { split: split === 'all' ? '' : split, limit: 20 }), [dataset.id, version, split])
  return (
    <Async state={rows}>
      {(r) => (<>
        <h4>Preview</h4>
        <DataTable rows={r.items} rowKey={(x) => x.index} columns={[{ key: 'index', label: '#', num: true }, { key: 'split', label: 'Split' },
          ...fields.map((f) => ({ key: f, label: f, clip: true, render: (x) => String(x.data[f] ?? '') }))]} />
        <p className="small faint">Showing {r.items.length} of {r.total} rows.</p>
      </>)}
    </Async>
  )
}

function Body({ project }) {
  const list = useAsync(() => api.datasets.list(project.id), [project.id])
  const [pick, setPick] = useState('')
  const datasets = list.data?.items || []
  const ds = datasets.find((d) => d.id === pick) || datasets[0]
  return (
    <div className="stack-lg">
      <UploadCard project={project} datasets={datasets} onDone={list.reload} />
      {list.error && <ErrorNotice error={list.error} onRetry={list.reload} />}
      {!list.loading && !list.error && !datasets.length && <EmptyState title="No datasets yet">Upload a CSV or JSONL file above. Its columns become the {'{{fields}}'} your prompts can use.</EmptyState>}
      {ds && (
        <Card title="Browse"><div className="stack">
          <SelectField label="Dataset" value={ds.id} options={datasets.map((d) => ({ value: d.id, label: `${d.name} (v${d.latest_version})` }))} onChange={(e) => setPick(e.target.value)} />
          <Inspect dataset={ds} />
        </div></Card>
      )}
    </div>
  )
}
export default function Datasets() {
  return (<div className="stack-lg"><PageHeader title="Datasets" subtitle="Test data for your prompts. Each upload becomes an immutable version." />
    <ProjectGate>{(project) => <Body project={project} />}</ProjectGate></div>)
}

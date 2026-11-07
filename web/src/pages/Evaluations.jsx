import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { fmtScore, fmtPct } from '../lib/format'
import { Async, Badge, Card, DataTable, EmptyState, Notice, PageHeader, ProjectGate } from '../components/ui'

function Catalog() {
  const state = useAsync(() => api.evaluators(), [])
  return (
    <Async state={state}>
      {(list) => (
        <div className="grid grid-2">
          {list.map((e) => (
            <Card key={e.type} title={<code>{e.type}</code>} actions={<Badge tone={e.kind === 'objective' ? 'success' : 'warning'}>{e.kind === 'objective' ? 'objective' : 'model judgment'}</Badge>}>
              <p>{e.description}</p>
              <p className="small muted" style={{ marginTop: 8 }}><b>Limits:</b> {e.limitations}</p>
              {e.needs_reference && <p className="small faint" style={{ marginTop: 6 }}>Needs a reference answer column.</p>}
            </Card>
          ))}
        </div>
      )}
    </Async>
  )
}

function Results({ project }) {
  const state = useAsync(() => api.experiments.list(project.id), [project.id])
  return (
    <Async state={state} empty={<EmptyState title="No experiment results yet">Run an experiment with metrics selected to see scores here.</EmptyState>}>
      {(data) => {
        const rows = data.items.flatMap((e) => Object.entries(e.summary?.metrics || {}).map(([name, m]) => ({ id: `${e.id}-${name}`, e, name, m })))
        return (
          <DataTable rows={rows} rowKey={(r) => r.id} empty="Your experiments have no metrics yet. Choose metrics when running one."
            columns={[{ key: 'e', label: 'Experiment', render: (r) => r.e.name }, { key: 'name', label: 'Metric', render: (r) => <code>{r.name}</code> },
              { key: 'kind', label: 'Kind', render: (r) => <Badge tone={r.m.kind === 'objective' ? 'success' : 'warning'}>{r.m.kind === 'objective' ? 'objective' : 'model judgment'}</Badge> },
              { key: 'mean', label: 'Mean score', num: true, render: (r) => fmtScore(r.m.mean_score) },
              { key: 'pass', label: 'Pass rate', num: true, render: (r) => fmtPct(r.m.pass_rate, 0) },
              { key: 'n', label: 'Scored', num: true, render: (r) => r.m.n_scored },
              { key: 'v', label: 'Prompt / dataset', render: (r) => `v${r.e.prompt_version} / v${r.e.dataset_version}` }]} />
        )
      }}
    </Async>
  )
}

export default function Evaluations() {
  return (
    <div className="stack-lg">
      <PageHeader title="Evaluations" subtitle="How answers are scored, and what each score can and cannot tell you." />
      <Notice tone="warning">No automatic metric proves an answer is factually correct, and no automated check can promise to catch every hallucination. Use scores to find answers worth reviewing.</Notice>
      <Catalog />
      <Card title="Results by experiment"><ProjectGate>{(project) => <Results project={project} />}</ProjectGate></Card>
    </div>
  )
}

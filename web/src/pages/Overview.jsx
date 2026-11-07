import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Circle } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { fmtInt, fmtMs, fmtDate } from '../lib/format'
import { useProject } from '../context/providers'
import { Async, Badge, Card, DataTable, ErrorNotice, Metric, PageHeader, StatusBadge } from '../components/ui'

function Checklist({ project }) {
  const state = useAsync(async () => {
    const [prompts, datasets, experiments, deployments, reqs] = await Promise.all([
      api.prompts.list(project.id), api.datasets.list(project.id), api.experiments.list(project.id),
      api.deployments.list(project.id), api.requests({ project_id: project.id, limit: 1 }),
    ])
    const live = deployments.some((d) => d.status === 'active')
    return [
      ['Run a prompt in the Playground', reqs.total > 0, '/app/playground'],
      ['Save a prompt as a version', prompts.total > 0, '/app/prompts'],
      ['Upload a dataset', datasets.total > 0, '/app/datasets'],
      ['Run an experiment and score it', experiments.total > 0, '/app/experiments'],
      ['Put a version live behind an API key', live, '/app/deployments'],
    ]
  }, [project.id])
  return (
    <Card title={`Getting started in "${project.name}"`}>
      <Async state={state} rows={4}>
        {(steps) => (
          <ol className="stack-sm" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {steps.map(([label, done, to]) => (
              <li key={label} className="row-between">
                <span className="row" style={{ gap: 10, color: done ? 'var(--text-3)' : 'var(--text)' }}>
                  {done ? <CheckCircle2 size={18} color="var(--success)" /> : <Circle size={18} color="var(--text-3)" />}{label}</span>
                {!done && <Link to={to} className="small row" style={{ gap: 4 }}>Go <ArrowRight size={14} /></Link>}
              </li>
            ))}
          </ol>
        )}
      </Async>
    </Card>
  )
}

export default function Overview() {
  const { project, projects } = useProject()
  const health = useAsync(() => api.health(), [])
  const reqs = useAsync(() => api.requests({ limit: 100, project_id: project?.id }), [project?.id])
  const rows = reqs.data?.items || []
  const ok = rows.filter((r) => r.status === 'success')
  const avg = ok.length ? ok.reduce((s, r) => s + (r.latency_ms || 0), 0) / ok.length : null
  const tokens = ok.reduce((s, r) => s + (r.total_tokens || 0), 0)
  return (
    <div className="stack-lg">
      <PageHeader title="Overview" subtitle="What is happening in your workspace right now." />
      <Async state={health}>
        {(h) => (
          <div className="grid grid-4">
            <Metric label="API" value={<Badge tone="success">Up</Badge>} />
            <Metric label="Database" value={<Badge tone={h.database.status === 'up' ? 'success' : 'danger'}>{h.database.status === 'up' ? 'Up' : 'Down'}</Badge>} />
            <Metric label="Default provider" value={<span style={{ fontSize: '1.2rem' }}>{h.llm_provider}</span>} />
            <Metric label="Management API" value={<Badge tone={h.admin_auth ? 'success' : 'warning'}>{h.admin_auth ? 'Token protected' : 'Open (local use)'}</Badge>} />
          </div>
        )}
      </Async>
      {project && <Checklist project={project} />}
      {!project && !projects.length && <Card><p className="muted">Create a project on the <Link to="/app/projects">Projects page</Link> to begin.</p></Card>}
      <Card title="Recent requests" actions={<Link to="/app/monitoring" className="small">Open monitoring</Link>}>
        {reqs.error ? <ErrorNotice error={reqs.error} onRetry={reqs.reload} /> : (
          <>
            <div className="grid grid-4" style={{ marginBottom: 16 }}>
              <Metric label="Requests (latest 100)" value={fmtInt(rows.length)} />
              <Metric label="Succeeded" value={fmtInt(ok.length)} />
              <Metric label="Avg latency" value={fmtMs(avg)} />
              <Metric label="Tokens" value={fmtInt(tokens)} />
            </div>
            <DataTable rows={rows.slice(0, 8)} empty="No requests yet. Run something in the Playground." rowKey={(r) => r.request_id}
              columns={[{ key: 'created_at', label: 'Time', render: (r) => fmtDate(r.created_at) },
                { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
                { key: 'model', label: 'Model', render: (r) => `${r.provider} / ${r.model}` },
                { key: 'latency_ms', label: 'Latency', num: true, render: (r) => fmtMs(r.latency_ms) },
                { key: 'total_tokens', label: 'Tokens', num: true, render: (r) => fmtInt(r.total_tokens) }]} />
          </>
        )}
      </Card>
    </div>
  )
}

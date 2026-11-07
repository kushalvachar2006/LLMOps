import { useState } from 'react'
import { Folder, Pencil, Plus } from 'lucide-react'
import { api } from '../lib/api'
import { fmtDate } from '../lib/format'
import { useAction } from '../lib/hooks'
import { useProject, useToast } from '../context/providers'
import { Button, Card, ConfirmButton, EmptyState, ErrorNotice, LoadingBlock, Modal, PageHeader, TextArea, TextField } from '../components/ui'

function ProjectForm({ initial, onSubmit, onCancel, busy, submitLabel }) {
  const [name, setName] = useState(initial?.name || '')
  const [description, setDescription] = useState(initial?.description || '')
  return (
    <form className="stack" onSubmit={(e) => { e.preventDefault(); onSubmit({ name, description }) }}>
      <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required autoFocus />
      <TextArea label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} style={{ minHeight: 70 }} />
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        {onCancel && <Button onClick={onCancel}>Cancel</Button>}
        <Button type="submit" variant="primary" loading={busy} disabled={!name.trim()}>{submitLabel}</Button>
      </div>
    </form>
  )
}

export default function Projects() {
  const { projects, loading, error, reload, select, project } = useProject()
  const toast = useToast()
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)
  const [run, busy] = useAction((e) => toast.error(e.message))

  const create = (b) => run(async () => { const p = await api.projects.create(b); toast.success(`Project "${p.name}" created.`); setCreating(false); await reload(); select(p.id) })
  const update = (b) => run(async () => { await api.projects.update(editing.id, b); toast.success('Project updated.'); setEditing(null); reload() })
  const remove = (p) => run(async () => { await api.projects.remove(p.id); toast.success('Project deleted.'); reload() })

  return (
    <div className="stack-lg">
      <PageHeader title="Projects" subtitle="A project groups prompts, datasets, experiments and deployments."
        actions={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>New project</Button>} />
      {error && <ErrorNotice error={error} onRetry={reload} />}
      {loading && !projects.length && <LoadingBlock />}
      {!loading && !error && !projects.length && (
        <EmptyState title="No projects yet" action={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Create your first project</Button>}>
          Everything you build lives inside a project.</EmptyState>
      )}
      <div className="grid grid-3">
        {projects.map((p) => (
          <Card key={p.id}>
            <div className="row-between"><h3 className="row" style={{ gap: 8 }}><Folder size={17} />{p.name}</h3>
              {project?.id === p.id && <span className="badge success">Selected</span>}</div>
            <p className="muted small" style={{ margin: '8px 0 12px', minHeight: 40 }}>{p.description || 'No description'}</p>
            <p className="faint small">Created {fmtDate(p.created_at)}</p>
            <div className="row" style={{ marginTop: 14 }}>
              {project?.id !== p.id && <Button size="sm" onClick={() => select(p.id)}>Select</Button>}
              <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(p)}>Edit</Button>
              <ConfirmButton label="Delete" confirmText={`Delete "${p.name}"? Projects that still contain prompts, datasets, experiments or deployments cannot be deleted.`} onConfirm={() => remove(p)} />
            </div>
          </Card>
        ))}
      </div>
      {creating && <Modal title="New project" onClose={() => setCreating(false)}><ProjectForm onSubmit={create} onCancel={() => setCreating(false)} busy={busy} submitLabel="Create project" /></Modal>}
      {editing && <Modal title="Edit project" onClose={() => setEditing(null)}><ProjectForm initial={editing} onSubmit={update} onCancel={() => setEditing(null)} busy={busy} submitLabel="Save changes" /></Modal>}
    </div>
  )
}

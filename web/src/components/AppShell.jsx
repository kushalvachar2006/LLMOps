import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Activity, BarChart3, Database, FlaskConical, Folder, GitCompare, LayoutDashboard, Menu, Moon, Rocket,
  Settings, Sparkles, Sun,
} from 'lucide-react'
import { ProjectProvider, useProject, useTheme } from '../context/providers'
import { api } from '../lib/api'
import { Notice } from './ui'

const NAV = [
  ['Start', [['/app', 'Overview', LayoutDashboard, true]]],
  ['Build', [['/app/playground', 'Playground', Sparkles], ['/app/prompts', 'Prompts', GitCompare], ['/app/datasets', 'Datasets', Database]]],
  ['Evaluate', [['/app/experiments', 'Experiments', FlaskConical], ['/app/evaluations', 'Evaluations', BarChart3]]],
  ['Ship and observe', [['/app/deployments', 'Deployments', Rocket], ['/app/monitoring', 'Monitoring', Activity]]],
  ['Workspace', [['/app/projects', 'Projects', Folder], ['/app/settings', 'Settings', Settings]]],
]

function useHealth() {
  const [h, setH] = useState({ state: 'checking' })
  useEffect(() => {
    let live = true
    const check = () => api.health()
      .then((d) => live && setH({ state: d.status === 'ok' ? 'ok' : 'degraded', data: d }))
      .catch(() => live && setH({ state: 'down' }))
    check()
    const t = setInterval(check, 30000)
    return () => { live = false; clearInterval(t) }
  }, [])
  return h
}

function Topbar({ onMenu }) {
  const { projects, project, select } = useProject()
  const { theme, toggle } = useTheme()
  const health = useHealth()
  const tone = { ok: 'success', degraded: 'warning', down: 'danger', checking: '' }[health.state]
  const label = { ok: 'Connected', degraded: 'Database down', down: 'API offline', checking: 'Checking' }[health.state]
  return (
    <header className="topbar">
      <button className="btn btn-ghost btn-icon menu-btn" onClick={onMenu} aria-label="Open navigation"><Menu size={20} /></button>
      <label className="sr-only" htmlFor="project-switch">Active project</label>
      <select id="project-switch" className="select" value={project?.id || ''} onChange={(e) => select(e.target.value)} disabled={!projects.length}>
        {!projects.length && <option value="">No projects yet</option>}
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <span className="grow" />
      <span className={`badge ${tone}`} title="Backend connection"><span className="dot" />{label}</span>
      <button className="btn btn-ghost btn-icon" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
    </header>
  )
}

export default function AppShell() {
  const [open, setOpen] = useState(false)
  const [authNeeded, setAuthNeeded] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => setOpen(false), [pathname])
  useEffect(() => {
    const on = () => setAuthNeeded(true)
    window.addEventListener('llmops:auth-required', on)
    return () => window.removeEventListener('llmops:auth-required', on)
  }, [])
  return (
    <ProjectProvider>
      <div className="shell">
        <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Primary">
          <Link to="/" className="brand"><span className="brand-mark"><svg width="16" height="16" viewBox="0 0 32 32" aria-hidden><path d="M8 22V10l8 6 8-6v12" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" /></svg></span>LLMOps</Link>
          {NAV.map(([title, items]) => (
            <nav key={title} className="nav-group" aria-label={title}>
              <div className="nav-title">{title}</div>
              {items.map(([to, label, Icon, end]) => (
                <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={17} aria-hidden />{label}</NavLink>
              ))}
            </nav>
          ))}
          <span className="grow" />
          <Link to="/" className="nav-link small">← Back to overview page</Link>
        </aside>
        {open && <div className="scrim" onClick={() => setOpen(false)} />}
        <div className="main">
          <Topbar onMenu={() => setOpen(true)} />
          {authNeeded && (
            <div className="page" style={{ paddingBottom: 0 }}>
              <Notice tone="warning">This server requires an admin token. <Link to="/app/settings">Enter it in Settings</Link> and reload.</Notice>
            </div>
          )}
          <main className="page"><Outlet /></main>
        </div>
      </div>
    </ProjectProvider>
  )
}

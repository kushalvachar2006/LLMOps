import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'

/* ---------- theme ---------- */
const ThemeCtx = createContext({ theme: 'dark', toggle: () => {} })
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('llmops.theme') || 'dark' } catch { return 'dark' }
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('llmops.theme', theme) } catch { /* private mode */ }
  }, [theme])
  const value = useMemo(() => ({ theme, toggle: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')) }), [theme])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}
export const useTheme = () => useContext(ThemeCtx)

/* ---------- toasts ---------- */
const ToastCtx = createContext(null)
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((kind, text) => {
    const id = Math.random().toString(36).slice(2)
    setItems((l) => [...l.slice(-3), { id, kind, text }])
    setTimeout(() => setItems((l) => l.filter((t) => t.id !== id)), 6000)
  }, [])
  const value = useMemo(() => ({
    success: (t) => push('success', t), error: (t) => push('error', t), info: (t) => push('info', t),
  }), [push])
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  )
}
export const useToast = () => useContext(ToastCtx)

/* ---------- selected project ---------- */
const ProjectCtx = createContext(null)
export function ProjectProvider({ children }) {
  const { data, error, loading, reload } = useAsync(() => api.projects.list(), [])
  const [selected, setSelected] = useState(() => {
    try { return localStorage.getItem('llmops.project') || '' } catch { return '' }
  })
  const projects = useMemo(() => data?.items || [], [data])
  const project = projects.find((p) => p.id === selected) || projects[0] || null
  const select = useCallback((id) => {
    setSelected(id)
    try { localStorage.setItem('llmops.project', id) } catch { /* ignore */ }
  }, [])
  const value = useMemo(
    () => ({ projects, project, select, reload, loading, error }),
    [projects, project, select, reload, loading, error],
  )
  return <ProjectCtx.Provider value={value}>{children}</ProjectCtx.Provider>
}
export const useProject = () => useContext(ProjectCtx)

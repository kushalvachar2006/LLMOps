import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, Check, CheckCircle2, Copy, Folder, Info, Loader2, Star, XCircle,
} from 'lucide-react'
import { ApiError } from '../lib/api'
import { getProviderKey, rememberKeys, setProviderKey } from '../lib/session'
import { useProject } from '../context/providers'

export const cx = (...a) => a.filter(Boolean).join(' ')

export function Button({ variant = 'secondary', size, icon: Icon, loading, children, className, ...rest }) {
  return (
    <button type="button" className={cx('btn', `btn-${variant}`, size && `btn-${size}`, className)}
      disabled={loading || rest.disabled} {...rest}>
      {loading ? <Loader2 size={16} className="spin" aria-hidden /> : Icon && <Icon size={16} aria-hidden />}
      {children}
    </button>
  )
}

export function Card({ title, actions, children, className }) {
  return (
    <section className={cx('card', className)}>
      {(title || actions) && (
        <div className="card-head">{title && <h3>{title}</h3>}{actions && <div className="row">{actions}</div>}</div>
      )}
      {children}
    </section>
  )
}

export const Badge = ({ tone, children }) => <span className={cx('badge', tone)}>{children}</span>

export function statusTone(status) {
  return ({ ready: 'success', healthy: 'success', active: 'success', completed: 'success', success: 'success',
    failed: 'danger', unhealthy: 'danger', error: 'danger', aborted: 'danger', partial: 'warning',
    validating: 'info', unknown: '', inactive: '', revoked: 'danger' })[status] ?? ''
}
export const StatusBadge = ({ status }) => <Badge tone={statusTone(status)}>{status}</Badge>

export function Field({ label, hint, error, children, className }) {
  const id = useId()
  const child = typeof children === 'function' ? children(id) : children
  return (
    <div className={cx('field', className)}>
      {label && <label htmlFor={id}>{label}</label>}
      {child}
      {hint && !error && <span className="hint">{hint}</span>}
      {error && <span className="error" role="alert">{error}</span>}
    </div>
  )
}
export const TextField = ({ label, hint, error, className, mono, ...rest }) => (
  <Field label={label} hint={hint} error={error} className={className}>
    {(id) => <input id={id} className={cx('input', mono && 'mono')} {...rest} />}
  </Field>
)
export const TextArea = ({ label, hint, error, className, mono, ...rest }) => (
  <Field label={label} hint={hint} error={error} className={className}>
    {(id) => <textarea id={id} className={cx('textarea', mono && 'mono')} {...rest} />}
  </Field>
)
export const SelectField = ({ label, hint, className, options, ...rest }) => (
  <Field label={label} hint={hint} className={className}>
    {(id) => (
      <select id={id} className="select" {...rest}>
        {options.map((o) => {
          const v = typeof o === 'object' ? o.value : o
          return <option key={v} value={v}>{typeof o === 'object' ? o.label : o}</option>
        })}
      </select>
    )}
  </Field>
)
export const Check_ = ({ label, ...rest }) => (
  <label className="check"><input type="checkbox" {...rest} />{label}</label>
)

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" className="tab" aria-selected={value === t.id}
          onClick={() => onChange(t.id)}>{t.label}</button>
      ))}
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-head row-between">
      <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
      {actions && <div className="row">{actions}</div>}
    </div>
  )
}

export function Metric({ label, value, hint }) {
  return <div className="metric"><div className="label">{label}</div><div className="value">{value}</div>{hint && <div className="hint">{hint}</div>}</div>
}

const NOTICE_ICON = { info: Info, warning: AlertTriangle, danger: XCircle, success: CheckCircle2 }
export function Notice({ tone = 'info', children }) {
  const Icon = NOTICE_ICON[tone]
  return <div className={cx('notice', tone)} role={tone === 'danger' ? 'alert' : undefined}><Icon size={18} aria-hidden /><div>{children}</div></div>
}

export function ErrorNotice({ error, onRetry }) {
  if (!error) return null
  const hints = {
    unreachable: 'Start the backend, then try again.',
    database_unavailable: 'The API is running but MongoDB is not reachable. Check MONGODB_URI.',
    missing_api_key: 'Add your model API key in the key field, or ask the server admin to configure one.',
  }
  return (
    <Notice tone="danger">
      <div><strong>{error.message}</strong></div>
      {error.category === 'unauthorized'
        ? <div className="small">This server needs an admin token. <Link to="/app/settings">Open Settings</Link> to enter it.</div>
        : hints[error.category] && <div className="small muted">{hints[error.category]}</div>}
      {error.requestId && <div className="small faint">Request ID: {error.requestId}</div>}
      {onRetry && <div style={{ marginTop: 8 }}><Button size="sm" onClick={onRetry}>Try again</Button></div>}
    </Notice>
  )
}

export const Spinner = () => <Loader2 className="spin" size={18} aria-label="Loading" />
export function LoadingBlock({ rows = 3 }) {
  return <div className="stack-sm" aria-busy="true">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ height: 22, width: `${100 - i * 12}%` }} />)}</div>
}

export function EmptyState({ icon: Icon = Folder, title, children, action }) {
  return <div className="empty"><Icon size={34} aria-hidden /><h3>{title}</h3>{children && <p>{children}</p>}{action && <div style={{ marginTop: 14 }}>{action}</div>}</div>
}

/** Renders loading / error / data states for an useAsync() result. */
export function Async({ state, children, rows, empty }) {
  if (state.loading && !state.data) return <LoadingBlock rows={rows} />
  if (state.error) return <ErrorNotice error={state.error} onRetry={state.reload} />
  // Nothing loaded yet (for example a hook waiting on a prerequisite): show the empty state, never crash.
  if (state.data == null) return empty ?? null
  if (empty && Array.isArray(state.data) && !state.data.length) return empty
  return children(state.data)
}

export function DataTable({ columns, rows, empty = 'Nothing to show.', rowKey }) {
  if (!rows?.length) return <p className="muted small">{empty}</p>
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((c) => <th key={c.key} className={c.num ? 'num' : ''}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i}>
              {columns.map((c) => <td key={c.key} className={cx(c.num && 'num', c.clip && 'clip')}>{c.render ? c.render(r) : r[c.key] ?? ''}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function CodeBlock({ code, label = 'Copy' }) {
  const [done, setDone] = useState(false)
  async function copy() {
    try { await navigator.clipboard.writeText(code); setDone(true); setTimeout(() => setDone(false), 1600) } catch { /* clipboard blocked */ }
  }
  return (
    <div className="code-block">
      <pre><code style={{ background: 'none', border: 0, padding: 0 }}>{code}</code></pre>
      <Button className="copy" size="sm" variant="ghost" icon={done ? Check : Copy} onClick={copy} aria-label={label}>{done ? 'Copied' : ''}</Button>
    </div>
  )
}

export function Modal({ title, onClose, children }) {
  const ref = useRef(null)
  useEffect(() => {
    ref.current?.focus()
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <h3 style={{ marginBottom: 12 }}>{title}</h3>{children}
      </div>
    </div>
  )
}

export function ConfirmButton({ label, confirmText, onConfirm, variant = 'danger', size = 'sm', ...rest }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant={variant} size={size} onClick={() => setOpen(true)} {...rest}>{label}</Button>
      {open && (
        <Modal title="Are you sure?" onClose={() => setOpen(false)}>
          <p className="muted">{confirmText}</p>
          <div className="row" style={{ marginTop: 18, justifyContent: 'flex-end' }}>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant={variant} onClick={() => { setOpen(false); onConfirm() }}>{label}</Button>
          </div>
        </Modal>
      )}
    </>
  )
}

export function Stars({ value, onChange }) {
  return (
    <div className="stars" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" className={cx('star', n <= (value || 0) && 'on')} role="radio"
          aria-checked={value === n} aria-label={`${n} star${n > 1 ? 's' : ''}`} onClick={() => onChange(n)}>
          <Star size={20} fill={n <= (value || 0) ? 'currentColor' : 'none'} />
        </button>
      ))}
    </div>
  )
}

/** Password box for a model API key. Memory only unless the user opts in on the Settings page. */
export function ProviderKeyField({ provider, label, serverKey, onChange }) {
  const [value, setValue] = useState(() => getProviderKey(provider))
  useEffect(() => { const v = getProviderKey(provider); setValue(v); onChange?.(v) }, [provider]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <TextField label={serverKey ? `${label} API key (optional)` : `${label} API key`} type="password"
      autoComplete="off" spellCheck={false} value={value} placeholder={serverKey ? 'Leave blank to use the server key' : 'Paste your key'}
      hint={rememberKeys() ? 'Kept for this browser tab only.' : 'Kept in memory only. It disappears when you reload.'}
      onChange={(e) => { const v = e.target.value.trim(); setValue(e.target.value); setProviderKey(provider, v); onChange?.(v) }} />
  )
}

/** Wraps pages that need a selected project. */
export function ProjectGate({ children }) {
  const { project, loading, error, reload } = useProject()
  if (loading && !project) return <LoadingBlock />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  if (!project) {
    return <EmptyState title="Create a project first" action={<Link className="btn btn-primary" to="/app/projects">Go to Projects</Link>}>
      Projects group your prompts, datasets, experiments and deployments.</EmptyState>
  }
  return children(project)
}

export const isApiError = (e) => e instanceof ApiError

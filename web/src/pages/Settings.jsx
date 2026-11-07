import { useState } from 'react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import {
  clearProviderKeys, getAdminToken, rememberKeys, setAdminToken, setRememberKeys,
} from '../lib/session'
import { useTheme, useToast } from '../context/providers'
import { Async, Button, Card, Notice, PageHeader, TextField } from '../components/ui'

export default function Settings() {
  const toast = useToast()
  const { theme, toggle } = useTheme()
  const health = useAsync(() => api.health(), [])
  const policy = useAsync(() => api.monitoring.policy(), [])
  const [token, setToken] = useState(getAdminToken())
  const [remember, setRemember] = useState(rememberKeys())
  return (
    <div className="stack-lg">
      <PageHeader title="Settings" subtitle="Connection, access and privacy for this browser." />
      <Card title="Connection">
        <Async state={health} rows={2}>
          {(h) => (
            <div className="stack">
              <dl className="kv">
                <dt>API</dt><dd>Reachable through this site (same origin)</dd>
                <dt>Database</dt><dd>{h.database.status}</dd>
                <dt>Default provider</dt><dd>{h.llm_provider}</dd>
                <dt>Admin token</dt><dd>{h.admin_auth ? 'Required by the server' : 'Not required (open local setup)'}</dd>
              </dl>
              {!h.admin_auth && <Notice tone="warning">The management API has no ADMIN_TOKEN, so anyone who can reach it can use it. That is fine on your own laptop. Set ADMIN_TOKEN before sharing or hosting.</Notice>}
            </div>
          )}
        </Async>
      </Card>
      <Card title="Admin token">
        <form className="stack" onSubmit={(e) => { e.preventDefault(); setAdminToken(token.trim()); toast.success(token.trim() ? 'Admin token saved for this tab.' : 'Admin token cleared.') }}>
          <TextField label="Token" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)}
            hint="Only needed if the server sets ADMIN_TOKEN. Kept in this tab's session storage and sent as the X-Admin-Token header. Closing the tab clears it." />
          <div className="row"><Button type="submit" variant="primary">Save token</Button>
            <Button onClick={() => { setToken(''); setAdminToken('') }}>Clear</Button></div>
        </form>
      </Card>
      <Card title="Model API keys">
        <div className="stack">
          <p className="muted small">Keys you paste in the Playground, Experiments and Deployments are sent to the server only with your own requests. They are never saved on the server.</p>
          <label className="check"><input type="checkbox" checked={remember} onChange={(e) => { setRemember(e.target.checked); setRememberKeys(e.target.checked) }} />
            Remember keys for this browser tab (uses session storage; cleared when the tab closes)</label>
          <div><Button onClick={() => { clearProviderKeys(); setRemember(false); toast.success('All stored keys were cleared.') }}>Clear keys now</Button></div>
        </div>
      </Card>
      <Card title="Data handling">
        <Async state={policy} rows={3}>
          {(p) => (
            <dl className="kv">
              <dt>Prompt and response text</dt><dd>{p.store_prompt_text ? 'Stored' : 'Not stored (default)'}</dd>
              <dt>Redaction of stored text</dt><dd>{p.redaction_enabled ? 'On' : 'Off'}</dd>
              <dt>Trace retention</dt><dd>{p.retention_days ? `${p.retention_days} days` : 'Kept until you delete them'}</dd>
              <dt>Never stored</dt><dd>{p.never_stored.join(', ')}</dd>
              <dt>Time to first token</dt><dd>{p.streaming_first_token_time}</dd>
              <dt>Retries</dt><dd>{p.retries}</dd>
            </dl>
          )}
        </Async>
      </Card>
      <Card title="Appearance"><Button onClick={toggle}>Switch to {theme === 'dark' ? 'light' : 'dark'} theme</Button></Card>
    </div>
  )
}

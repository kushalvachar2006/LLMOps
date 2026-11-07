/* Where secrets live in the browser.
 *  - Admin token: sessionStorage (cleared when the tab closes).
 *  - Model API keys: memory only by default. Optionally kept in sessionStorage for the tab.
 * A browser app cannot hide a secret from someone using that browser, so nothing here is
 * baked into the build, and nothing is ever written to localStorage. */
const ADMIN = 'llmops.admin'
const KEYS = 'llmops.keys'
const REMEMBER = 'llmops.remember'

const memory = new Map()
const safe = (fn, fallback) => { try { return fn() } catch { return fallback } }

export const getAdminToken = () => safe(() => sessionStorage.getItem(ADMIN) || '', '')
export const setAdminToken = (v) => safe(() => (v ? sessionStorage.setItem(ADMIN, v) : sessionStorage.removeItem(ADMIN)))

export const rememberKeys = () => safe(() => sessionStorage.getItem(REMEMBER) === '1', false)
export function setRememberKeys(on) {
  safe(() => {
    if (on) { sessionStorage.setItem(REMEMBER, '1'); sessionStorage.setItem(KEYS, JSON.stringify(Object.fromEntries(memory))) }
    else { sessionStorage.removeItem(REMEMBER); sessionStorage.removeItem(KEYS) }
  })
}
export function getProviderKey(provider) {
  if (memory.has(provider)) return memory.get(provider)
  const stored = safe(() => JSON.parse(sessionStorage.getItem(KEYS) || '{}'), {})
  return stored[provider] || ''
}
export function setProviderKey(provider, value) {
  if (value) memory.set(provider, value); else memory.delete(provider)
  if (rememberKeys()) safe(() => sessionStorage.setItem(KEYS, JSON.stringify(Object.fromEntries(memory))))
}
export function clearProviderKeys() {
  memory.clear()
  safe(() => { sessionStorage.removeItem(KEYS); sessionStorage.removeItem(REMEMBER) })
}

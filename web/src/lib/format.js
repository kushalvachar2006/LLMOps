export const fmtInt = (n) => (n == null ? 'n/a' : Number(n).toLocaleString())
export const fmtMs = (n) => (n == null ? 'n/a' : `${Math.round(n).toLocaleString()} ms`)
export const fmtPct = (n, digits = 1) => (n == null ? 'n/a' : `${(n * 100).toFixed(digits)}%`)
export const fmtDate = (s) => (s ? String(s).replace('T', ' ').slice(0, 19) : 'never')
export const fmtScore = (n) => (n == null ? 'n/a' : Number(n).toFixed(2))
export const errMessage = (e) => (e?.message || 'Something went wrong.')
export function isoRange(preset, custom) {
  const end = new Date()
  const day = 86400000
  if (preset === 'custom' && custom?.start && custom?.end) {
    return { start: new Date(`${custom.start}T00:00:00Z`).toISOString(),
      end: new Date(new Date(`${custom.end}T00:00:00Z`).getTime() + day).toISOString() }
  }
  const span = { '24h': day, '7d': 7 * day, '30d': 30 * day }[preset] || 7 * day
  return { start: new Date(end.getTime() - span).toISOString(), end: end.toISOString() }
}
export function download(name, text, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  URL.revokeObjectURL(url)
}

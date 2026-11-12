async function json(res) {
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* not json */ }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json()
}

function qs(params = {}) {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined && v !== false && v !== 0),
  )
  const s = new URLSearchParams(clean).toString()
  return s ? `?${s}` : ''
}

const post = (url, body) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  }).then(json)

export const api = {
  health: () => fetch('/api/health').then(json),
  stats: (source) => fetch(`/api/stats${qs({ source })}`).then(json),
  alerts: (filters) => fetch(`/api/alerts${qs(filters)}`).then(json),
  alert: (id, source) => fetch(`/api/alerts/${id}${qs({ source })}`).then(json),
  signals: (params) => fetch(`/api/signals${qs(params)}`).then(json),
  ingest: () => post('/api/ingest/live'),
  reset: () => post('/api/demo/reset'),
  analyze: (body) => post('/api/analyze', body),
}

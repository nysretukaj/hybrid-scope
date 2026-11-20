async function json(res) {
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* not json */ }
    const err = new Error(`${res.status}: ${detail}`)
    err.status = res.status
    throw err
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

// Every read takes the UI language, so the backend returns titles, summaries, explanations,
// rationales, briefs and place names already translated.
export const api = {
  health: () => fetch('/api/health').then(json),
  stats: (source, hours, lang) => fetch(`/api/stats${qs({ source, hours, lang })}`).then(json),
  geo: (source, hours, lang) => fetch(`/api/geo${qs({ source, hours, lang })}`).then(json),
  aiSummary: (id, source, lang) => fetch(`/api/alerts/${id}/ai-summary${qs({ source, lang })}`).then(json),
  classify: (signalId, category, subcategory) => post(`/api/signals/${signalId}/classification`, { category, subcategory }),
  alerts: (filters, lang) => fetch(`/api/alerts${qs({ ...filters, lang })}`).then(json),
  alert: (id, source, lang) => fetch(`/api/alerts/${id}${qs({ source, lang })}`).then(json),
  brief: (id, source, lang) => fetch(`/api/alerts/${id}/brief${qs({ source, lang })}`).then(json),
  replay: (id, source, lang) => fetch(`/api/alerts/${id}/replay${qs({ source, lang })}`).then(json),
  feedback: (id, source, verdict, note) => post(`/api/alerts/${id}/feedback${qs({ source })}`, { verdict, note }),
  clearFeedback: (id) => fetch(`/api/alerts/${id}/feedback`, { method: 'DELETE' }).then(json),
  notify: (id, source) => post(`/api/alerts/${id}/notify${qs({ source })}`),
  notifyTest: () => post('/api/notify/test'),
  graph: (source, lang) => fetch(`/api/graph${qs({ source, lang })}`).then(json),
  signals: (params, lang) => fetch(`/api/signals${qs({ ...params, lang })}`).then(json),
  ingest: () => post('/api/ingest/live'),
  reset: () => post('/api/demo/reset'),
  analyze: (body, lang) => post('/api/analyze', { ...body, lang }),
  samples: () => fetch('/api/analyze/samples').then(json),
  snapshot: () => post('/api/demo/snapshot'),
  // local AI (Ollama + model trained on our data)
  mlStatus: () => fetch('/api/ml/status').then(json),
  mlTrain: () => post('/api/ml/train'),
  mlLabel: (limit) => post(`/api/ml/label${qs({ limit })}`),
  mlExport: () => post('/api/ml/export'),
  mlCreateModel: () => post('/api/ml/create-model'),
  verifyAi: (id, source, lang) => post(`/api/alerts/${id}/verify-ai${qs({ source, lang })}`),
  signalImage: (id) => post(`/api/signals/${id}/image`),
}

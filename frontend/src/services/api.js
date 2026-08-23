// Thin API client. Vite proxies /api to the FastAPI backend in dev.

const BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const payload = await response.json()
      detail = payload.detail || detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return response.status === 204 ? null : response.json()
}

export const api = {
  // calls
  startDemoCall: (body) => request('/calls/demo/start', { method: 'POST', body }),
  startPhoneCall: (body) => request('/calls/start', { method: 'POST', body }),
  scenarios: () => request('/calls/demo/scenarios'),
  sendTurn: (callId, text) => request(`/calls/${callId}/turn`, { method: 'POST', body: { text } }),
  endCall: (callId) => request(`/calls/${callId}/end`, { method: 'POST' }),
  listCalls: (params = '') => request(`/calls${params}`),
  getCall: (callId) => request(`/calls/${callId}`),
  transcript: (callId) => request(`/calls/${callId}/transcript`),

  // leads
  listLeads: (query = '') => request(`/leads${query}`),
  getLead: (id) => request(`/leads/${id}`),
  patchLead: (id, body) => request(`/leads/${id}`, { method: 'PATCH', body }),
  scoreExplanation: (id) => request(`/leads/${id}/score-explanation`),

  // whatsapp + callbacks
  whatsappMessages: (query = '') => request(`/whatsapp/messages${query}`),
  sendWhatsApp: (body) => request('/whatsapp/send', { method: 'POST', body }),
  callbacks: (query = '') => request(`/callbacks${query}`),
  createCallback: (body) => request('/callbacks', { method: 'POST', body }),
  parseTime: (text) => request('/callbacks/parse', { method: 'POST', body: { text } }),
  updateCallback: (id, status) => request(`/callbacks/${id}?status=${status}`, { method: 'PATCH' }),

  // dashboard
  stats: () => request('/dashboard/stats'),
  activity: () => request('/dashboard/recent-activity'),
  funnel: () => request('/dashboard/funnel'),
  health: () => request('/dashboard/health'),

  // config
  storeConfig: () => request('/config/store'),
  patchStoreConfig: (body) => request('/config/store', { method: 'PATCH', body }),
  providers: () => request('/config/providers'),
  switchProvider: (body) => request('/config/providers', { method: 'POST', body }),

  // training
  trainingResults: () => request('/training/results'),
  generateDataset: (body) => request('/training/generate-dataset', { method: 'POST', body }),
  trainModel: (body) => request('/training/train', { method: 'POST', body }),
  classify: (text) => request('/training/classify', { method: 'POST', body: { text } }),
  benchmark: () => request('/training/benchmark', { method: 'POST' }),
  peekDataset: (limit = 25) => request(`/training/dataset?limit=${limit}`),
}

export function websocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${BASE}/ws`
}

// API / WebSocket の接続先。
//   /config.js の window.__API_BASE_URL__ が空なら同一オリジン (Nginx が中継)。
//   S3 ホスティング時は "http://<EC2のIP>:8000" が入っている。
const runtimeUrl = typeof window !== 'undefined' ? window.__API_BASE_URL__ : undefined
export const API_BASE_URL = String(runtimeUrl ?? '').trim().replace(/\/$/, '')
export const WS_URL = (API_BASE_URL || window.location.origin).replace(/^http/, 'ws') + '/api/ws'

const TOKEN_KEY = 'chat_token'
export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' } }
export const setToken = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch {} }

/** 画像パス (/uploads/...) を API の URL に直す */
export const assetUrl = (path) => (path?.startsWith('/') ? `${API_BASE_URL}${path}` : path)

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

async function request(path, { method = 'GET', body, formData } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method, headers, body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : (data.detail?.[0]?.msg || `HTTP ${res.status}`)
    throw new ApiError(res.status, detail)
  }
  return data
}

export const api = {
  signup: (username, display_name, password) => request('/api/auth/signup', { method: 'POST', body: { username, display_name, password } }),
  login: (username, password) => request('/api/auth/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/me'),
  updateMe: (patch) => request('/api/me', { method: 'PATCH', body: patch }),
  users: (q = '') => request(`/api/users?q=${encodeURIComponent(q)}`),
  rooms: () => request('/api/rooms'),
  room: (id) => request(`/api/rooms/${id}`),
  createRoom: (type, member_ids, name) => request('/api/rooms', { method: 'POST', body: { type, member_ids, name } }),
  messages: (roomId, { before, after } = {}) =>
    request(`/api/rooms/${roomId}/messages?limit=50${before ? `&before=${encodeURIComponent(before)}` : ''}${after ? `&after=${encodeURIComponent(after)}` : ''}`),
  sendMessage: (roomId, type, content) => request(`/api/rooms/${roomId}/messages`, { method: 'POST', body: { type, content } }),
  uploadImage: (roomId, file) => { const fd = new FormData(); fd.append('file', file); return request(`/api/rooms/${roomId}/images`, { method: 'POST', formData: fd }) },
  markRead: (roomId, messageId) => request(`/api/rooms/${roomId}/read`, { method: 'POST', body: { message_id: messageId } }),
  unsend: (roomId, messageId) => request(`/api/rooms/${roomId}/messages/${messageId}`, { method: 'DELETE' }),
  info: () => request('/api/info'),
  publicSettings: () => request('/api/settings/public'),
  settings: () => request('/api/settings'),
  testSettings: (body) => request('/api/settings/test', { method: 'POST', body }),
  saveSettings: (body) => request('/api/settings', { method: 'PUT', body }),
}

/** WebSocket 接続。切れたら自動再接続する。 */
export function connectWS({ onEvent, onStatus }) {
  let ws = null
  let closed = false
  let retry = 0
  let pingTimer = null

  function open() {
    if (closed) return
    onStatus?.('connecting')
    ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(getToken())}`)
    ws.onopen = () => { retry = 0; onStatus?.('online'); pingTimer = setInterval(() => send({ type: 'ping' }), 25000) }
    ws.onmessage = (ev) => { try { onEvent(JSON.parse(ev.data)) } catch {} }
    ws.onclose = (ev) => {
      clearInterval(pingTimer)
      onStatus?.('offline')
      if (closed || ev.code === 4401) return
      const wait = Math.min(1000 * 2 ** retry++, 15000)
      setTimeout(open, wait)
    }
    ws.onerror = () => {}
  }
  function send(obj) { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj)) }
  open()
  return { send, close: () => { closed = true; clearInterval(pingTimer); ws?.close() } }
}

// API の接続先の決め方 (優先順):
//   1. /config.js の window.__API_BASE_URL__   … 実行時設定。S3 ホスティング時はここに EC2 の URL を書く
//   2. 空文字                                   … 同じオリジンの /api を使う (Nginx が FastAPI へ中継)
const runtimeUrl = typeof window !== 'undefined' ? window.__API_BASE_URL__ : undefined
export const API_BASE_URL = String(runtimeUrl ?? '').trim().replace(/\/$/, '')

async function request(path, options) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  info: () => request('/api/info'),
  listMessages: () => request('/api/messages'),
  createMessage: (author, body) =>
    request('/api/messages', { method: 'POST', body: JSON.stringify({ author, body }) }),
}

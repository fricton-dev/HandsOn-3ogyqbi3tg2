const WEEK = ['日', '月', '火', '水', '木', '金', '土']

export function formatTime(iso) {
  const d = new Date(iso)
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function dateKey(iso) {
  const d = new Date(iso)
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

export function formatDateLabel(iso) {
  const d = new Date(iso)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diff = Math.round((today - target) / 86400000)
  if (diff === 0) return '今日'
  if (diff === 1) return '昨日'
  const y = d.getFullYear() !== now.getFullYear() ? `${d.getFullYear()}年` : ''
  return `${y}${d.getMonth() + 1}月${d.getDate()}日(${WEEK[d.getDay()]})`
}

/** トーク一覧用: 今日なら時刻、昨日なら「昨日」、それ以外は M/D */
export function formatListTime(iso) {
  if (!iso) return ''
  const label = formatDateLabel(iso)
  if (label === '今日') return formatTime(iso)
  if (label === '昨日') return '昨日'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export function previewOf(msg) {
  if (!msg) return ''
  if (msg.deleted) return 'メッセージの送信を取り消しました'
  if (msg.type === 'sticker') return '[スタンプ]'
  if (msg.type === 'image') return '[画像]'
  return msg.content
}

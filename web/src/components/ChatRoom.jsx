import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Avatar from './Avatar.jsx'
import MessageBubble from './MessageBubble.jsx'
import StickerPicker from './StickerPicker.jsx'
import { BackIcon, ImageIcon, SendIcon, SmileIcon } from './Icons.jsx'
import { dateKey, formatDateLabel } from '../utils.js'

export default function ChatRoom({ me, room, messages, hasMore, typing, onlineIds, onBack, onLoadOlder, onTyping }) {
  const [text, setText] = useState('')
  const [showStickers, setShowStickers] = useState(false)
  const [error, setError] = useState('')
  const [lightbox, setLightbox] = useState(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const listRef = useRef(null)
  const fileRef = useRef(null)
  const textRef = useRef(null)
  const lastTypingSent = useRef(0)
  const stickToBottom = useRef(true)

  // 既読人数: 自分以外のメンバーで last_read >= msg.id の人数
  const others = room.members.filter((m) => m.id !== me.id)
  const readCountOf = (msg) => others.filter((m) => m.last_read_message_id >= msg.id).length

  // 新しいメッセージが来たら、下にいる時だけ自動スクロール
  useEffect(() => {
    const el = listRef.current
    if (!el) return
    if (stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [messages.length, typing])

  useEffect(() => { listRef.current && (listRef.current.scrollTop = listRef.current.scrollHeight) }, [room.id])

  function onScroll() {
    const el = listRef.current
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  async function loadOlder() {
    const el = listRef.current
    const before = el.scrollHeight
    setLoadingOlder(true)
    try { await onLoadOlder() } finally { setLoadingOlder(false) }
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight - before })
  }

  async function send(type, content) {
    setError('')
    try {
      stickToBottom.current = true
      await api.sendMessage(room.id, type, content)
    } catch (e) {
      setError(e.message)
    }
  }

  function sendText() {
    const t = text.trim()
    if (!t) return
    setText('')
    textRef.current?.focus()
    send('text', t)
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      sendText()
    }
  }

  function onChangeText(e) {
    setText(e.target.value)
    const now = Date.now()
    if (now - lastTypingSent.current > 2000) { lastTypingSent.current = now; onTyping() }
  }

  async function onPickImage(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setError('')
    try { stickToBottom.current = true; await api.uploadImage(room.id, file) } catch (err) { setError(err.message) }
  }

  async function unsend(msg) {
    if (!window.confirm('このメッセージの送信を取り消しますか？\n（相手の画面からも消えます）')) return
    try { await api.unsend(room.id, msg.id) } catch (e) { setError(e.message) }
  }

  const online = room.type === 'direct' ? onlineIds.includes(room.partner_id) : null
  const onlineMembers = room.type === 'group' ? others.filter((m) => onlineIds.includes(m.id)).length : 0

  // 日付区切りとアバター表示の判定
  const items = []
  let prevKey = null
  let prevSender = null
  for (const msg of messages) {
    const k = dateKey(msg.created_at)
    if (k !== prevKey) { items.push({ kind: 'date', key: `d-${k}`, label: formatDateLabel(msg.created_at) }); prevKey = k; prevSender = null }
    items.push({ kind: 'msg', key: msg.id, msg, showAvatar: msg.sender.id !== prevSender || msg.type === 'system' })
    prevSender = msg.type === 'system' ? null : msg.sender.id
  }

  return (
    <main className="chat">
      <header className="chat-header">
        <button className="icon-btn back" onClick={onBack} aria-label="戻る"><BackIcon width={22} height={22} /></button>
        <Avatar name={room.name} color={room.avatar_color} size={40} online={!!online} group={room.type === 'group'} />
        <div className="chat-title">
          <div className="name">{room.name}{room.type === 'group' && <span className="count">{room.members.length}</span>}</div>
          <div className="sub">
            {room.type === 'direct' ? (online ? 'オンライン' : 'オフライン') : `${room.members.map((m) => m.display_name).join('、')}${onlineMembers ? ` ・ ${onlineMembers} 人がオンライン` : ''}`}
          </div>
        </div>
      </header>

      <div className="message-list" ref={listRef} onScroll={onScroll}>
        {hasMore && (
          <div className="load-older"><button onClick={loadOlder} disabled={loadingOlder}>{loadingOlder ? '読み込み中...' : '以前のメッセージを読む'}</button></div>
        )}
        {items.map((it) => it.kind === 'date'
          ? <div key={it.key} className="date-sep"><span>{it.label}</span></div>
          : <MessageBubble key={it.key} msg={it.msg} me={me} room={room} readCount={readCountOf(it.msg)}
              showAvatar={it.showAvatar} onUnsend={unsend} onOpenImage={setLightbox} />)}
        {typing && (
          <div className="typing"><span className="dots"><i /><i /><i /></span>{typing.user.display_name} が入力中</div>
        )}
      </div>

      {showStickers && <StickerPicker onPick={(s) => { setShowStickers(false); send('sticker', s) }} />}
      {error && <div className="chat-error">{error}</div>}

      <footer className="composer">
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={onPickImage} />
        <button className="icon-btn" title="画像を送る" onClick={() => fileRef.current?.click()}><ImageIcon width={22} height={22} /></button>
        <button className={`icon-btn ${showStickers ? 'active' : ''}`} title="スタンプ" onClick={() => setShowStickers((v) => !v)}><SmileIcon width={22} height={22} /></button>
        <textarea ref={textRef} rows={1} placeholder="メッセージを入力" title="Enter で送信、Shift+Enter で改行"
          value={text} onChange={onChangeText} onKeyDown={onKeyDown} />
        <button className="send" onClick={sendText} disabled={!text.trim()} aria-label="送信"><SendIcon width={18} height={18} /></button>
      </footer>

      {lightbox && (
        <div className="modal-backdrop lightbox" onClick={() => setLightbox(null)}>
          <img src={lightbox} alt="画像" />
        </div>
      )}
    </main>
  )
}

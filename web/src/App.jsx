import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, connectWS, getToken, setToken } from './api.js'
import Login from './components/Login.jsx'
import { idGte, idMax } from './utils.js'
import Sidebar from './components/Sidebar.jsx'
import ChatRoom from './components/ChatRoom.jsx'
import { ChatIcon } from './components/Icons.jsx'

export default function App() {
  const [me, setMe] = useState(null)
  const [booting, setBooting] = useState(!!getToken())
  const [rooms, setRooms] = useState([])
  const [currentRoomId, setCurrentRoomId] = useState(null)
  const [messagesByRoom, setMessagesByRoom] = useState({})   // roomId -> { list, hasMore }
  const [typingByRoom, setTypingByRoom] = useState({})       // roomId -> { user, until }
  const [onlineIds, setOnlineIds] = useState([])
  const [wsStatus, setWsStatus] = useState('offline')
  const [storage, setStorage] = useState({ mode: 'postgres', table: '', region: '', image_bucket: '' })
  const wsRef = useRef(null)
  const currentRoomRef = useRef(null)
  currentRoomRef.current = currentRoomId
  const meRef = useRef(null)
  meRef.current = me

  const loadStorage = useCallback(() => api.publicSettings().then(setStorage).catch(() => {}), [])

  // ---------- 起動時: 公開設定 (モード) を取り、トークンがあれば自動ログイン ----------
  useEffect(() => {
    loadStorage()
    if (!getToken()) return
    api.me().then(setMe).catch(() => setToken('')).finally(() => setBooting(false))
  }, [loadStorage])

  const logout = useCallback(async () => {
    try { await api.logout() } catch {}
    setToken('')
    setMe(null); setRooms([]); setCurrentRoomId(null); setMessagesByRoom({})
  }, [])

  // ---------- 既読を送る ----------
  const roomsRef = useRef([])
  roomsRef.current = rooms
  const markRead = useCallback((roomId, messageId) => {
    if (!messageId) return
    const room = roomsRef.current.find((r) => r.id === roomId)
    if (room && idGte(room.my_last_read_message_id, messageId) && room.unread_count === 0) return
    setRooms((rs) => rs.map((r) => r.id === roomId
      ? { ...r, unread_count: 0, my_last_read_message_id: idMax(r.my_last_read_message_id, messageId) }
      : r))
    api.markRead(roomId, messageId).catch(() => {})
  }, [])

  // ---------- WebSocket イベント ----------
  const handleEvent = useCallback((ev) => {
    switch (ev.type) {
      case 'message': {
        const msg = ev.message
        const isCurrent = currentRoomRef.current === ev.room_id && document.hasFocus()
        setMessagesByRoom((m) => {
          const cur = m[ev.room_id]
          if (!cur) return m
          if (cur.list.some((x) => x.id === msg.id)) return m
          return { ...m, [ev.room_id]: { ...cur, list: [...cur.list, msg] } }
        })
        setRooms((rs) => {
          const exists = rs.some((r) => r.id === ev.room_id)
          if (!exists) { api.room(ev.room_id).then((room) => setRooms((x) => x.some((r) => r.id === room.id) ? x : [room, ...x])).catch(() => {}); return rs }
          return rs.map((r) => r.id !== ev.room_id ? r : {
            ...r,
            last_message: msg,
            last_activity_at: msg.created_at,
            unread_count: (msg.sender.id === meRef.current?.id || isCurrent) ? r.unread_count : r.unread_count + 1,
            members: r.members.map((mb) => mb.id === msg.sender.id ? { ...mb, last_read_message_id: idMax(mb.last_read_message_id, msg.id) } : mb),
          }).sort((a, b) => (b.last_activity_at || '').localeCompare(a.last_activity_at || ''))
        })
        if (isCurrent && msg.sender.id !== meRef.current?.id) markRead(ev.room_id, msg.id)
        setTypingByRoom((t) => { const n = { ...t }; delete n[ev.room_id]; return n })
        break
      }
      case 'message_deleted': {
        const msg = ev.message
        setMessagesByRoom((m) => {
          const cur = m[ev.room_id]
          if (!cur) return m
          return { ...m, [ev.room_id]: { ...cur, list: cur.list.map((x) => x.id === msg.id ? msg : x) } }
        })
        setRooms((rs) => rs.map((r) => r.id === ev.room_id && r.last_message?.id === msg.id ? { ...r, last_message: msg } : r))
        break
      }
      case 'read':
        setRooms((rs) => rs.map((r) => r.id !== ev.room_id ? r : {
          ...r,
          members: r.members.map((mb) => mb.id === ev.user_id ? { ...mb, last_read_message_id: ev.last_read_message_id } : mb),
        }))
        break
      case 'typing':
        setTypingByRoom((t) => ({ ...t, [ev.room_id]: { user: ev.user, until: Date.now() + 3000 } }))
        break
      case 'presence':
        setOnlineIds(ev.online_user_ids)
        break
      case 'room_created':
        setRooms((rs) => rs.some((r) => r.id === ev.room.id) ? rs : [ev.room, ...rs])
        break
      default:
        break
    }
  }, [markRead])

  // ---------- 再同期: ルーム一覧と、開いているルームのメッセージを取り直す ----------
  const resync = useCallback(async () => {
    try {
      const rs = await api.rooms()
      setRooms(rs)
      const rid = currentRoomRef.current
      if (rid) {
        const res = await api.messages(rid)
        setMessagesByRoom((m) => ({ ...m, [rid]: { list: res.messages, hasMore: res.has_more } }))
        const last = res.messages[res.messages.length - 1]
        if (last && document.hasFocus()) {
          const room = rs.find((r) => r.id === rid)
          if (!room || !idGte(room.my_last_read_message_id, last.id)) {
            setRooms((cur) => cur.map((r) => r.id === rid ? { ...r, unread_count: 0, my_last_read_message_id: last.id } : r))
            api.markRead(rid, last.id).catch(() => {})
          }
        }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) logout()
    }
  }, [logout])

  // ---------- ログイン後: WS 接続 (接続できたら再同期) ----------
  useEffect(() => {
    if (!me) return
    resync()
    const ws = connectWS({
      onEvent: handleEvent,
      onStatus: (st) => { setWsStatus(st); if (st === 'online') resync() },
    })
    wsRef.current = ws
    return () => { ws.close(); wsRef.current = null }
  }, [me, handleEvent, resync])

  // 入力中表示のタイムアウト処理
  useEffect(() => {
    const t = setInterval(() => {
      setTypingByRoom((cur) => {
        const now = Date.now()
        const next = Object.fromEntries(Object.entries(cur).filter(([, v]) => v.until > now))
        return Object.keys(next).length === Object.keys(cur).length ? cur : next
      })
    }, 1000)
    return () => clearInterval(t)
  }, [])

  // タブのタイトルに未読数
  useEffect(() => {
    const unread = rooms.reduce((n, r) => n + (r.unread_count || 0), 0)
    document.title = unread > 0 ? `(${unread}) Talk` : 'Talk'
  }, [rooms])

  // ---------- ルームを開く ----------
  const openRoom = useCallback(async (roomId) => {
    setCurrentRoomId(roomId)
    if (!messagesByRoom[roomId]) {
      try {
        const res = await api.messages(roomId)
        setMessagesByRoom((m) => ({ ...m, [roomId]: { list: res.messages, hasMore: res.has_more } }))
        const last = res.messages[res.messages.length - 1]
        if (last) markRead(roomId, last.id)
      } catch {}
    } else {
      const list = messagesByRoom[roomId].list
      const last = list[list.length - 1]
      if (last) markRead(roomId, last.id)
    }
  }, [messagesByRoom, markRead])

  const loadOlder = useCallback(async (roomId) => {
    const cur = messagesByRoom[roomId]
    if (!cur || !cur.hasMore || cur.list.length === 0) return
    const res = await api.messages(roomId, { before: cur.list[0].id })
    setMessagesByRoom((m) => ({ ...m, [roomId]: { list: [...res.messages, ...m[roomId].list], hasMore: res.has_more } }))
  }, [messagesByRoom])

  const sendTyping = useCallback((roomId) => wsRef.current?.send({ type: 'typing', room_id: roomId }), [])

  const onRoomCreated = useCallback((room) => {
    setRooms((rs) => rs.some((r) => r.id === room.id) ? rs : [room, ...rs])
    openRoom(room.id)
  }, [openRoom])

  // ---------- 共有モード (DynamoDB): 他の EC2 からの書き込みをポーリングで拾う ----------
  useEffect(() => {
    if (!me || storage.mode !== 'dynamodb') return
    let busy = false
    const tick = async () => {
      if (busy || document.hidden) return
      busy = true
      try {
        const rid = currentRoomRef.current
        const [rs, res] = await Promise.all([api.rooms(), rid ? api.messages(rid) : null])
        setRooms(rs)
        if (rid && res) {
          setMessagesByRoom((m) => {
            const cur = m[rid]
            if (!cur) return m
            const byId = new Map(cur.list.map((x) => [x.id, x]))
            let changed = false
            for (const msg of res.messages) {
              const old = byId.get(msg.id)
              if (!old) { byId.set(msg.id, msg); changed = true }
              else if (old.deleted !== msg.deleted) { byId.set(msg.id, msg); changed = true }
            }
            if (!changed) return m
            const list = [...byId.values()].sort((a, b) => (idGte(a.id, b.id) ? 1 : -1))
            return { ...m, [rid]: { ...cur, list } }
          })
          const last = res.messages[res.messages.length - 1]
          const room = rs.find((r) => r.id === rid)
          if (last && document.hasFocus() && room && !idGte(room.my_last_read_message_id, last.id)) {
            markRead(rid, last.id)
          }
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) logout()
      } finally {
        busy = false
      }
    }
    const t = setInterval(tick, 2500)
    return () => clearInterval(t)
  }, [me, storage.mode, markRead, logout])

  // ---------- 設定が保存されたら: ログアウトしてモードを取り直す ----------
  const onSettingsSaved = useCallback(async (pub) => {
    setStorage(pub)
    setToken('')
    setMe(null); setRooms([]); setCurrentRoomId(null); setMessagesByRoom({})
  }, [])

  // ウィンドウがフォーカスを得たら、開いているルームを既読にする
  useEffect(() => {
    const onFocus = () => {
      const rid = currentRoomRef.current
      const list = rid && messagesByRoom[rid]?.list
      if (list?.length) markRead(rid, list[list.length - 1].id)
    }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [messagesByRoom, markRead])

  if (booting) return <div className="boot">読み込み中...</div>
  if (!me) return <Login storage={storage} onLogin={(user) => setMe(user)} />

  const currentRoom = rooms.find((r) => r.id === currentRoomId) || null

  return (
    <div className={`app ${currentRoomId ? 'show-chat' : ''}`}>
      <Sidebar
        me={me} rooms={rooms} currentRoomId={currentRoomId} onlineIds={onlineIds} wsStatus={wsStatus}
        onOpenRoom={openRoom} onRoomCreated={onRoomCreated} onLogout={logout}
        onUpdateMe={(patch) => api.updateMe(patch).then(setMe)}
        storage={storage} onSettingsSaved={onSettingsSaved}
      />
      {currentRoom ? (
        <ChatRoom
          key={currentRoom.id}
          me={me} room={currentRoom} onlineIds={onlineIds}
          messages={messagesByRoom[currentRoom.id]?.list || []}
          hasMore={!!messagesByRoom[currentRoom.id]?.hasMore}
          typing={typingByRoom[currentRoom.id]}
          imagesEnabled={storage.mode !== 'dynamodb' || !!storage.image_bucket}
          onBack={() => setCurrentRoomId(null)}
          onLoadOlder={() => loadOlder(currentRoom.id)}
          onTyping={() => sendTyping(currentRoom.id)}
        />
      ) : (
        <main className="chat empty">
          <div className="empty-state">
            <div className="empty-icon"><ChatIcon width={56} height={56} strokeWidth={1.2} /></div>
            <p>トークを選択してください</p>
          </div>
        </main>
      )}
    </div>
  )
}

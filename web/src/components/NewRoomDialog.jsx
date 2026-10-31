import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Avatar from './Avatar.jsx'
import { CloseIcon } from './Icons.jsx'

export default function NewRoomDialog({ onlineIds, onClose, onCreated }) {
  const [users, setUsers] = useState([])
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState([])
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.users(q).then(setUsers).catch(() => {}) }, [q])

  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])

  async function create() {
    if (selected.length === 0) return
    setBusy(true); setError('')
    try {
      const room = selected.length === 1
        ? await api.createRoom('direct', selected)
        : await api.createRoom('group', selected, name.trim() || undefined)
      onCreated(room)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>新しいトーク</h2>
          <button className="icon-btn" onClick={onClose} aria-label="閉じる"><CloseIcon /></button>
        </header>
        <input className="search" placeholder="名前で検索" value={q} onChange={(e) => setQ(e.target.value)} />
        <ul className="user-list">
          {users.map((u) => (
            <li key={u.id} onClick={() => toggle(u.id)} className={selected.includes(u.id) ? 'selected' : ''}>
              <input type="checkbox" readOnly checked={selected.includes(u.id)} />
              <Avatar name={u.display_name} color={u.avatar_color} size={36} online={onlineIds.includes(u.id)} />
              <div className="user-text">
                <div className="name">{u.display_name}</div>
                <div className="sub">@{u.username}{u.status_message ? ` ・ ${u.status_message}` : ''}</div>
              </div>
            </li>
          ))}
          {users.length === 0 && <li className="none">ユーザーが見つかりません</li>}
        </ul>
        {selected.length >= 2 && (
          <input className="search" placeholder="グループ名（省略可）" value={name} onChange={(e) => setName(e.target.value)} maxLength={50} />
        )}
        {error && <p className="login-error">{error}</p>}
        <button className="primary" disabled={selected.length === 0 || busy} onClick={create}>
          {selected.length <= 1 ? 'トークを開始' : `${selected.length} 人でグループを作成`}
        </button>
      </div>
    </div>
  )
}

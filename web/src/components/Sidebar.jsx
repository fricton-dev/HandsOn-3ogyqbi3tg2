import { useState } from 'react'
import Avatar from './Avatar.jsx'
import NewRoomDialog from './NewRoomDialog.jsx'
import S3Export from './S3Export.jsx'
import SettingsDialog from './SettingsDialog.jsx'
import { formatListTime, previewOf } from '../utils.js'

export default function Sidebar({ me, rooms, currentRoomId, onlineIds, wsStatus, onOpenRoom, onRoomCreated, onLogout, onUpdateMe, storage, onSettingsSaved }) {
  const [q, setQ] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [showS3, setShowS3] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [editStatus, setEditStatus] = useState(false)
  const [status, setStatus] = useState(me.status_message || '')

  const filtered = rooms.filter((r) => !q || r.name.includes(q) || previewOf(r.last_message).includes(q))

  async function saveStatus() {
    setEditStatus(false)
    if (status !== me.status_message) await onUpdateMe({ status_message: status })
  }

  return (
    <aside className="sidebar">
      <header className="sidebar-header">
        <Avatar name={me.display_name} color={me.avatar_color} size={44} online={wsStatus === 'online'} />
        <div className="me-text">
          <div className="name">{me.display_name}</div>
          {editStatus ? (
            <input className="status-input" autoFocus value={status} maxLength={100}
              onChange={(e) => setStatus(e.target.value)} onBlur={saveStatus}
              onKeyDown={(e) => e.key === 'Enter' && saveStatus()} placeholder="ステータスメッセージ" />
          ) : (
            <button className="status" onClick={() => setEditStatus(true)} title="クリックして編集">
              {me.status_message || 'ステータスメッセージを設定'}
            </button>
          )}
        </div>
        <button className="icon-btn" title="新しいトーク" onClick={() => setShowNew(true)}>＋</button>
      </header>

      <div className="search-wrap">
        <input className="search" placeholder="トークを検索" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      <ul className="room-list">
        {filtered.map((r) => {
          const online = r.type === 'direct' && onlineIds.includes(r.partner_id)
          return (
            <li key={r.id} className={r.id === currentRoomId ? 'active' : ''} onClick={() => onOpenRoom(r.id)}>
              <Avatar name={r.name} color={r.avatar_color} size={48} online={online} group={r.type === 'group'} />
              <div className="room-text">
                <div className="row1">
                  <span className="name">{r.name}</span>
                  {r.type === 'group' && <span className="count">{r.members.length}</span>}
                  <span className="time">{formatListTime(r.last_activity_at)}</span>
                </div>
                <div className="row2">
                  <span className="preview">{previewOf(r.last_message) || 'まだメッセージはありません'}</span>
                  {r.unread_count > 0 && <span className="unread">{r.unread_count > 99 ? '99+' : r.unread_count}</span>}
                </div>
              </div>
            </li>
          )
        })}
        {filtered.length === 0 && <li className="none">トークがありません</li>}
      </ul>

      <footer className="sidebar-footer">
        <span className={`ws ${wsStatus}`}>{wsStatus === 'online' ? '● 接続中' : wsStatus === 'connecting' ? '○ 再接続中...' : '○ オフライン'}</span>
        <span className={`mode-pill ${storage?.mode === 'dynamodb' ? 'shared' : 'local'}`} title={storage?.mode === 'dynamodb' ? `DynamoDB: ${storage.table}` : 'この EC2 の PostgreSQL'}>
          {storage?.mode === 'dynamodb' ? '共有' : 'ローカル'}
        </span>
        <button className="link" onClick={() => setShowSettings(true)}>⚙️ 設定</button>
        <button className="link" onClick={() => setShowS3(true)}>📦 S3 出力</button>
        <button className="link" onClick={onLogout}>ログアウト</button>
      </footer>

      {showNew && <NewRoomDialog onlineIds={onlineIds} onClose={() => setShowNew(false)} onCreated={(room) => { setShowNew(false); onRoomCreated(room) }} />}
      {showS3 && <S3Export onClose={() => setShowS3(false)} />}
      {showSettings && <SettingsDialog onClose={() => setShowSettings(false)} onSaved={onSettingsSaved} />}
    </aside>
  )
}

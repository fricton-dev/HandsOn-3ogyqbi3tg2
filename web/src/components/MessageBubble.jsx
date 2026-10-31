import { useState } from 'react'
import Avatar from './Avatar.jsx'
import { assetUrl } from '../api.js'
import { formatTime } from '../utils.js'
import { MoreIcon } from './Icons.jsx'

/**
 * メッセージ 1 件。自分のものは右・緑、相手のものは左・白。
 * readCount: 自分以外で「このメッセージまで読んだ」人数。1:1 では「既読」、グループでは「既読 N」。
 */
export default function MessageBubble({ msg, me, room, readCount, showAvatar, onUnsend, onOpenImage }) {
  const [menu, setMenu] = useState(false)
  const mine = msg.sender.id === me.id

  if (msg.type === 'system') {
    return <div className="system-msg"><span>{msg.content}</span></div>
  }

  const time = formatTime(msg.created_at)
  const readLabel = mine && readCount > 0 ? (room.type === 'direct' ? '既読' : `既読 ${readCount}`) : ''

  let body
  if (msg.deleted) {
    body = <div className="bubble deleted">メッセージの送信を取り消しました</div>
  } else if (msg.type === 'sticker') {
    body = <div className="sticker">{msg.content}</div>
  } else if (msg.type === 'image') {
    body = (
      <button className="image-msg" onClick={() => onOpenImage(assetUrl(msg.content))}>
        <img src={assetUrl(msg.content)} alt="画像" loading="lazy" />
      </button>
    )
  } else {
    body = <div className="bubble">{msg.content}</div>
  }

  return (
    <div className={`msg ${mine ? 'mine' : 'theirs'}`} onMouseLeave={() => setMenu(false)}>
      {!mine && (
        <div className="msg-avatar">
          {showAvatar && <Avatar name={msg.sender.display_name} color={msg.sender.avatar_color} size={36} />}
        </div>
      )}
      <div className="msg-main">
        {!mine && showAvatar && room.type === 'group' && <div className="sender">{msg.sender.display_name}</div>}
        <div className="msg-row">
          {mine && (
            <div className="meta">
              {readLabel && <span className="read">{readLabel}</span>}
              <span className="time">{time}</span>
            </div>
          )}
          {mine && !msg.deleted && (
            <button className="more" onClick={() => setMenu((v) => !v)} aria-label="メニュー"><MoreIcon width={16} height={16} /></button>
          )}
          <div className="msg-body" onContextMenu={(e) => { if (mine && !msg.deleted) { e.preventDefault(); setMenu(true) } }}>
            {body}
            {menu && (
              <div className="msg-menu">
                <button onClick={() => { setMenu(false); onUnsend(msg) }}>送信取消</button>
              </div>
            )}
          </div>
          {!mine && <div className="meta"><span className="time">{time}</span></div>}
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { STICKER_PACKS } from '../stickers.js'

export default function StickerPicker({ onPick }) {
  const [packId, setPackId] = useState(STICKER_PACKS[0].id)
  const pack = STICKER_PACKS.find((p) => p.id === packId)
  return (
    <div className="sticker-picker">
      <div className="sticker-tabs">
        {STICKER_PACKS.map((p) => (
          <button key={p.id} className={p.id === packId ? 'active' : ''} onClick={() => setPackId(p.id)}>
            <span className="tab-icon">{p.items[0]}</span>{p.name}
          </button>
        ))}
      </div>
      <div className="sticker-grid">
        {pack.items.map((s) => (
          <button key={s} onClick={() => onPick(s)} aria-label={`スタンプ ${s}`}>{s}</button>
        ))}
      </div>
    </div>
  )
}

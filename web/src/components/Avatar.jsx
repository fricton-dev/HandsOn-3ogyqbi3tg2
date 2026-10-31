export default function Avatar({ name = '', color = '#999', size = 40, online, group }) {
  const initial = group ? '👥' : (name.trim().replace(/^.*?\s+/, '')[0] || name[0] || '?')
  return (
    <span className="avatar" style={{ width: size, height: size, background: color, fontSize: size * 0.42 }}>
      {initial}
      {online && <span className="online-dot" />}
    </span>
  )
}

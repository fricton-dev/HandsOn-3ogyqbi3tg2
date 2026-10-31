import { PeopleIcon } from './Icons.jsx'

export default function Avatar({ name = '', color = '#999', size = 40, online, group }) {
  const initial = name.trim().replace(/^.*?\s+/, '')[0] || name[0] || '?'
  return (
    <span className="avatar" style={{ width: size, height: size, background: color, fontSize: size * 0.42 }}>
      {group ? <PeopleIcon width={size * 0.5} height={size * 0.5} /> : initial}
      {online && <span className="online-dot" />}
    </span>
  )
}

import { useState } from 'react'
import { api, setToken } from '../api.js'

const DEMO = [
  { username: 'akari', label: '佐藤 あかり' },
  { username: 'kenta', label: '鈴木 けんた' },
  { username: 'mio', label: '田中 みお' },
]

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e, demoUser) {
    e?.preventDefault()
    setBusy(true); setError('')
    try {
      const res = demoUser
        ? await api.login(demoUser, 'password')
        : mode === 'login'
          ? await api.login(username.trim(), password)
          : await api.signup(username.trim(), displayName.trim(), password)
      setToken(res.token)
      onLogin(res.user)
    } catch (err) {
      setError(err.message || String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <form className="login-card" onSubmit={submit}>
        <div className="login-logo">💬</div>
        <h1>チャット</h1>
        <div className="tabs">
          <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>ログイン</button>
          <button type="button" className={mode === 'signup' ? 'active' : ''} onClick={() => setMode('signup')}>新規登録</button>
        </div>
        <label>ユーザー名
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" placeholder="英数字 3〜30 文字" required />
        </label>
        {mode === 'signup' && (
          <label>表示名
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="例: 山田 太郎" required maxLength={50} />
          </label>
        )}
        <label>パスワード
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={4} />
        </label>
        {error && <p className="login-error">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>{busy ? '...' : mode === 'login' ? 'ログイン' : '登録してはじめる'}</button>

        <div className="demo">
          <p>デモアカウントでログイン（パスワード: password）</p>
          <div className="demo-buttons">
            {DEMO.map((d) => (
              <button key={d.username} type="button" onClick={(e) => submit(e, d.username)} disabled={busy}>{d.label}</button>
            ))}
          </div>
          <p className="hint">別のブラウザ（またはシークレットウィンドウ）で別のアカウントにログインすると、既読やリアルタイム配信を試せます。</p>
        </div>
      </form>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api, API_BASE_URL } from './api.js'
import S3Export from './S3Export.jsx'

export default function App() {
  const [info, setInfo] = useState(null)
  const [messages, setMessages] = useState([])
  const [author, setAuthor] = useState('')
  const [body, setBody] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setError('')
    try {
      const [i, m] = await Promise.all([api.info(), api.listMessages()])
      setInfo(i)
      setMessages(m)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function onSubmit(e) {
    e.preventDefault()
    if (!author.trim() || !body.trim()) return
    setError('')
    try {
      await api.createMessage(author.trim(), body.trim())
      setBody('')
      await load()
    } catch (e) {
      setError(String(e.message || e))
    }
  }

  const apiOk = !!info
  const dbOk = !!info?.db_ok

  return (
    <main className="container">
      <h1>AWS 研修サンプルアプリ</h1>
      <p className="lead">
        この画面は <strong>Web (Nginx/React)</strong> → <strong>API (FastAPI)</strong> →{' '}
        <strong>DB (PostgreSQL)</strong> の 3 層で動いています。
      </p>

      <section className="card">
        <h2>接続状況</h2>
        <ul className="status">
          <li>
            <span className="label">画面の配信元</span>
            <code>{window.location.origin}</code>
          </li>
          <li>
            <span className="label">API の接続先</span>
            <code>{API_BASE_URL || '(同一オリジン /api)'}</code>
          </li>
          <li>
            <span className={`badge ${apiOk ? 'ok' : 'ng'}`}>{apiOk ? 'OK' : 'NG'}</span>
            API サーバー {info && <small>(ホスト名: {info.api_hostname})</small>}
          </li>
          <li>
            <span className={`badge ${dbOk ? 'ok' : 'ng'}`}>{dbOk ? 'OK' : 'NG'}</span>
            データベース {info && <small>({info.db_version?.split(' on ')[0]})</small>}
          </li>
        </ul>
        {loading && <p>読み込み中...</p>}
        {error && (
          <div className="error">
            <strong>エラー:</strong> {error}
            <p className="hint">
              ヒント: セキュリティグループで 80/8000 番ポートが開いているか、
              <code>docker compose ps</code> で 3 つのコンテナが起動しているかを確認してください。
            </p>
          </div>
        )}
      </section>

      <section className="card">
        <h2>メッセージ一覧（DB から取得）</h2>
        {messages.length === 0 && !loading && <p>メッセージはまだありません。</p>}
        <ul className="messages">
          {messages.map((m) => (
            <li key={m.id}>
              <span className="author">{m.author}</span>
              <span className="body">{m.body}</span>
              <time>{new Date(m.created_at).toLocaleString('ja-JP')}</time>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>メッセージを追加（DB へ保存）</h2>
        <form onSubmit={onSubmit} className="form">
          <input
            placeholder="名前"
            value={author}
            maxLength={50}
            onChange={(e) => setAuthor(e.target.value)}
          />
          <input
            placeholder="メッセージ"
            value={body}
            maxLength={200}
            onChange={(e) => setBody(e.target.value)}
          />
          <button type="submit" disabled={!apiOk}>送信</button>
        </form>
        <p className="hint">
          送信後にページを再読み込みしても残っていれば、DB に保存されています。
        </p>
      </section>

      <S3Export />
    </main>
  )
}

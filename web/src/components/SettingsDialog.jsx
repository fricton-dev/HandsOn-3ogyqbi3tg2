import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { ChevronIcon, CloseIcon } from './Icons.jsx'

const REGIONS = ['ap-northeast-1', 'ap-northeast-3', 'us-east-1', 'us-west-2', 'ap-southeast-1', 'eu-west-1']

// 履歴の保存先 (この環境の PostgreSQL / 共有 DynamoDB) を切り替える
export default function SettingsDialog({ onClose, onSaved }) {
  const [form, setForm] = useState({ mode: 'postgres', table: '', region: 'ap-northeast-1', endpoint_url: '', access_key_id: '', secret_access_key: '', image_bucket: '', s3_endpoint_url: '' })
  const [loaded, setLoaded] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)   // { ok, text }

  useEffect(() => {
    api.settings().then((s) => {
      setForm({ mode: s.mode, table: s.table || '', region: s.region || 'ap-northeast-1', endpoint_url: s.endpoint_url || '',
        access_key_id: s.access_key_id || '', secret_access_key: s.has_secret ? '********' : '',
        image_bucket: s.image_bucket || '', s3_endpoint_url: s.s3_endpoint_url || '' })
      setAdvanced(!!(s.endpoint_url || s.access_key_id || s.s3_endpoint_url))
      setLoaded(true)
    }).catch((e) => setResult({ ok: false, text: e.message }))
  }, [])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const shared = form.mode === 'dynamodb'

  async function test() {
    setBusy('test'); setResult(null)
    try { const r = await api.testSettings(form); setResult({ ok: true, text: r.detail }) }
    catch (e) { setResult({ ok: false, text: e.message }) }
    finally { setBusy('') }
  }

  async function save() {
    const msg = shared
      ? '共有モードに切り替えます。切り替え後はログアウトされ、共有テーブルのアカウントでログインし直します。'
      : 'この環境の PostgreSQL に戻します。切り替え後はログアウトされます。'
    if (!window.confirm(msg)) return
    setBusy('save'); setResult(null)
    try {
      const r = await api.saveSettings(form)
      setResult({ ok: true, text: `保存しました。${r.detail || ''}` })
      setTimeout(() => { onClose(); onSaved(r.public) }, 800)
    } catch (e) {
      setResult({ ok: false, text: e.message })
    } finally { setBusy('') }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal settings" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>保存先</h2>
          <button className="icon-btn" onClick={onClose} aria-label="閉じる"><CloseIcon /></button>
        </header>

        <div className="mode-options">
          <label className={`mode-option ${!shared ? 'checked' : ''}`}>
            <input type="radio" name="mode" value="postgres" checked={!shared} onChange={set('mode')} />
            <div>
              <div className="title">この環境の PostgreSQL</div>
              <div className="desc">自分の EC2 の中だけで動きます。デモアカウントが使えます。</div>
            </div>
          </label>
          <label className={`mode-option ${shared ? 'checked' : ''}`}>
            <input type="radio" name="mode" value="dynamodb" checked={shared} onChange={set('mode')} />
            <div>
              <div className="title">共有 DynamoDB テーブル</div>
              <div className="desc">講師が用意したテーブルを全員で使います。アカウントもテーブル側に作ります。</div>
            </div>
          </label>
        </div>

        {shared && (
          <>
            <label>テーブル名
              <input value={form.table} onChange={set('table')} placeholder="handson-chat" disabled={!loaded} />
            </label>
            <label>リージョン
              <input list="regions" value={form.region} onChange={set('region')} />
              <datalist id="regions">{REGIONS.map((r) => <option key={r} value={r} />)}</datalist>
            </label>
            <label>画像用 S3 バケット
              <input value={form.image_bucket} onChange={set('image_bucket')} placeholder="handson-chat-images" />
            </label>
            <p className="hint">
              共有モードの画像はこのバケットに保存され、どの EC2 からも見られます。空欄のままだと共有モードでは画像を送れません。
              テーブルと同じリージョンにあるものを指定してください。
            </p>
            <p className="hint">
              認証情報は EC2 に付けた IAM ロールを使います。ロールを付けられない場合だけ、詳細設定でアクセスキーを入力してください。
            </p>
            <button type="button" className="link toggle" onClick={() => setAdvanced((v) => !v)}>
              <ChevronIcon open={advanced} width={14} height={14} />詳細設定
            </button>
            {advanced && (
              <div className="advanced">
                <label>アクセスキー ID
                  <input value={form.access_key_id} onChange={set('access_key_id')} autoComplete="off" />
                </label>
                <label>シークレットアクセスキー
                  <input type="password" value={form.secret_access_key} onChange={set('secret_access_key')} autoComplete="new-password" />
                </label>
                <label>DynamoDB エンドポイント URL
                  <input value={form.endpoint_url} onChange={set('endpoint_url')} placeholder="通常は空欄" />
                </label>
                <label>S3 エンドポイント URL
                  <input value={form.s3_endpoint_url} onChange={set('s3_endpoint_url')} placeholder="通常は空欄" />
                </label>
                <p className="hint">アクセスキーはこの EC2 のデータベースに平文で保存されます。研修中の一時的な利用に限ってください。</p>
              </div>
            )}
          </>
        )}

        {result && <p className={`settings-result ${result.ok ? 'ok' : 'ng'}`}>{result.text}</p>}

        <div className="settings-actions">
          {shared && <button type="button" className="secondary" onClick={test} disabled={!!busy || !form.table}>{busy === 'test' ? '確認中...' : '接続テスト'}</button>}
          <button type="button" className="primary" onClick={save} disabled={!!busy || (shared && !form.table)}>{busy === 'save' ? '保存中...' : '保存して切り替え'}</button>
        </div>
        <p className="hint">
          共有モードでは、他の EC2 からの書き込みを数秒おきに取得します。入力中とオンラインの表示は、同じ EC2 に接続している相手にだけ届きます。
        </p>
      </div>
    </div>
  )
}

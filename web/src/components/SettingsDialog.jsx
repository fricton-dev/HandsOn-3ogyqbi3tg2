import { useEffect, useState } from 'react'
import { api } from '../api.js'

const REGIONS = ['ap-northeast-1', 'ap-northeast-3', 'us-east-1', 'us-west-2', 'ap-southeast-1', 'eu-west-1']

/**
 * チャット履歴の保存先を切り替える設定画面。
 *   ローカル: この EC2 の PostgreSQL (研修の前半)
 *   共有:     講師が用意した DynamoDB テーブル (研修生全員でチャット)
 */
export default function SettingsDialog({ onClose, onSaved }) {
  const [form, setForm] = useState({ mode: 'postgres', table: '', region: 'ap-northeast-1', endpoint_url: '', access_key_id: '', secret_access_key: '' })
  const [loaded, setLoaded] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)   // { ok, text }

  useEffect(() => {
    api.settings().then((s) => {
      setForm({ mode: s.mode, table: s.table || '', region: s.region || 'ap-northeast-1', endpoint_url: s.endpoint_url || '',
        access_key_id: s.access_key_id || '', secret_access_key: s.has_secret ? '********' : '' })
      setAdvanced(!!(s.endpoint_url || s.access_key_id))
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
      ? `共有モードに切り替えます。\n切り替え後はいったんログアウトし、共有テーブルのアカウントで登録 / ログインし直します。よろしいですか？`
      : `ローカルモードに戻します。\n切り替え後はいったんログアウトします。よろしいですか？`
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
          <h2>⚙️ チャット履歴の保存先</h2>
          <button className="icon-btn" onClick={onClose} aria-label="閉じる">✕</button>
        </header>

        <div className="mode-options">
          <label className={`mode-option ${!shared ? 'checked' : ''}`}>
            <input type="radio" name="mode" value="postgres" checked={!shared} onChange={set('mode')} />
            <div>
              <div className="title">ローカル（この EC2 の PostgreSQL）</div>
              <div className="desc">自分の環境だけで完結。デモアカウントが使えます。</div>
            </div>
          </label>
          <label className={`mode-option ${shared ? 'checked' : ''}`}>
            <input type="radio" name="mode" value="dynamodb" checked={shared} onChange={set('mode')} />
            <div>
              <div className="title">共有（講師が用意した DynamoDB テーブル）</div>
              <div className="desc">研修生全員で同じトークを使えます。アカウントも共有テーブル側に作ります。</div>
            </div>
          </label>
        </div>

        {shared && (
          <>
            <label>テーブル名
              <input value={form.table} onChange={set('table')} placeholder="例: handson-chat" disabled={!loaded} />
            </label>
            <label>リージョン
              <input list="regions" value={form.region} onChange={set('region')} />
              <datalist id="regions">{REGIONS.map((r) => <option key={r} value={r} />)}</datalist>
            </label>
            <p className="hint">
              認証情報は EC2 に付けた IAM ロールを使います（推奨）。ロールが無い場合だけ「詳細設定」でアクセスキーを入力してください。
            </p>
            <button type="button" className="link" onClick={() => setAdvanced((v) => !v)}>{advanced ? '▾ 詳細設定を隠す' : '▸ 詳細設定（アクセスキー / エンドポイント）'}</button>
            {advanced && (
              <div className="advanced">
                <label>アクセスキー ID（任意）
                  <input value={form.access_key_id} onChange={set('access_key_id')} autoComplete="off" />
                </label>
                <label>シークレットアクセスキー（任意）
                  <input type="password" value={form.secret_access_key} onChange={set('secret_access_key')} autoComplete="new-password" />
                </label>
                <label>エンドポイント URL（通常は空。DynamoDB Local の検証用）
                  <input value={form.endpoint_url} onChange={set('endpoint_url')} placeholder="http://dynamodb-local:8000" />
                </label>
                <p className="hint">⚠️ アクセスキーはこの EC2 のローカル DB に保存されます。研修用の一時的な用途に限ってください。</p>
              </div>
            )}
          </>
        )}

        {result && <p className={`settings-result ${result.ok ? 'ok' : 'ng'}`}>{result.ok ? '✅ ' : '❌ '}{result.text}</p>}

        <div className="settings-actions">
          {shared && <button type="button" className="secondary" onClick={test} disabled={!!busy || !form.table}>{busy === 'test' ? '確認中...' : '接続テスト'}</button>}
          <button type="button" className="primary" onClick={save} disabled={!!busy || (shared && !form.table)}>{busy === 'save' ? '保存中...' : '保存して切り替え'}</button>
        </div>
        <p className="hint">
          共有モードでは、他の EC2 からの書き込みは数秒おきに取りに行きます。入力中表示とオンライン表示は同じ EC2 に接続している人同士でのみ動きます。
        </p>
      </div>
    </div>
  )
}

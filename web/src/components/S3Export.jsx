import { useState } from 'react'
import JSZip from 'jszip'

/**
 * S3 静的ホスティング用の zip を作る。
 * 表示中のページ自身 (index.html + assets) を集め、API 接続先を書いた config.js を同梱する。
 */
export default function S3Export({ onClose }) {
  const defaultApi = `${window.location.protocol}//${window.location.hostname}:8000`
  const [apiUrl, setApiUrl] = useState(defaultApi)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState('')

  async function download() {
    setBusy(true); setLog('')
    try {
      const zip = new JSZip()
      const origin = window.location.origin
      const indexRes = await fetch('/index.html', { cache: 'no-store' })
      if (!indexRes.ok) throw new Error('index.html を取得できません')
      const html = await indexRes.text()
      zip.file('index.html', html)

      const urls = new Set()
      document.querySelectorAll('script[src], link[rel="stylesheet"][href]').forEach((el) => {
        const u = new URL(el.getAttribute('src') || el.getAttribute('href'), origin)
        if (u.origin === origin && u.pathname !== '/config.js') urls.add(u.pathname)
      })
      for (const m of html.matchAll(/(?:src|href)="(\/[^"]+\.(?:js|css|svg|png|ico|woff2?))"/g)) {
        if (m[1] !== '/config.js') urls.add(m[1])
      }
      let count = 1
      for (const path of urls) {
        const res = await fetch(path, { cache: 'no-store' })
        if (!res.ok) throw new Error(`${path} を取得できません (HTTP ${res.status})`)
        zip.file(path.replace(/^\//, ''), await res.arrayBuffer())
        count++
      }
      const apiBase = apiUrl.trim().replace(/\/$/, '')
      zip.file('config.js', `// S3 用に自動生成。API の接続先を指定する\nwindow.__API_BASE_URL__ = ${JSON.stringify(apiBase)};\n`)
      zip.file('README_S3.txt', [
        'このフォルダの中身をそのまま S3 バケットのルートにアップロードしてください。',
        '', '  aws s3 sync . s3://<バケット名> --delete', '',
        `API 接続先: ${apiBase}`,
        '接続先を変えたい場合は config.js を書き換えるだけで済みます (再ビルド不要)。',
        'S3 側で「静的ウェブサイトホスティング」を有効にし、index と error の両方を index.html にしてください。', '',
      ].join('\n'))

      const blob = await zip.generateAsync({ type: 'blob' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 's3-static-site.zip'
      a.click()
      URL.revokeObjectURL(a.href)
      setLog(`✅ ${count + 2} ファイルを zip にしました (API: ${apiBase})`)
    } catch (e) {
      setLog(`❌ ${e.message || e}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal s3export-panel" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>📦 S3 用の静的ファイルを出力</h2>
          <button className="icon-btn" onClick={onClose} aria-label="閉じる">✕</button>
        </header>
        <p>この画面の HTML / JS / CSS と、API の接続先を書いた <code>config.js</code> を zip にまとめます。解凍して中身を S3 バケットにアップロードしてください。</p>
        <label>API の接続先（EC2 の IP と 8000 番）
          <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
        </label>
        <button className="primary" onClick={download} disabled={busy}>{busy ? '作成中...' : 'zip をダウンロード'}</button>
        {log && <p className="s3export-log">{log}</p>}
      </div>
    </div>
  )
}

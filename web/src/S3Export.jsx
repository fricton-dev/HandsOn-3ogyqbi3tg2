import { useState } from 'react'
import JSZip from 'jszip'

/**
 * 画面右下のパネル。
 * 今表示しているページ自身 (index.html + assets) を集め、API 接続先を書いた config.js を同梱した
 * zip を作ってダウンロードする。中身をそのまま S3 バケットにアップロードすれば静的ホスティングで動く。
 */
export default function S3Export() {
  const [open, setOpen] = useState(false)
  const defaultApi = `${window.location.protocol}//${window.location.hostname}:8000`
  const [apiUrl, setApiUrl] = useState(defaultApi)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState('')

  async function download() {
    setBusy(true)
    setLog('')
    try {
      const zip = new JSZip()
      const origin = window.location.origin

      // 1. index.html
      const indexRes = await fetch('/index.html', { cache: 'no-store' })
      if (!indexRes.ok) throw new Error('index.html を取得できません')
      zip.file('index.html', await indexRes.text())

      // 2. ページが読み込んでいる JS / CSS (同一オリジンのもの)
      const urls = new Set()
      document.querySelectorAll('script[src], link[rel="stylesheet"][href]').forEach((el) => {
        const raw = el.getAttribute('src') || el.getAttribute('href')
        const u = new URL(raw, origin)
        if (u.origin !== origin) return
        if (u.pathname === '/config.js') return // 3 で作り直す
        urls.add(u.pathname)
      })
      // index.html に書かれているが未ロードの asset も拾う (modulepreload 等)
      const html = await zip.file('index.html').async('string')
      for (const m of html.matchAll(/(?:src|href)="(\/[^"]+\.(?:js|css|svg|png|ico|woff2?))"/g)) {
        if (m[1] !== '/config.js') urls.add(m[1])
      }

      const files = []
      for (const path of urls) {
        const res = await fetch(path, { cache: 'no-store' })
        if (!res.ok) throw new Error(`${path} を取得できません (HTTP ${res.status})`)
        zip.file(path.replace(/^\//, ''), await res.arrayBuffer())
        files.push(path)
      }

      // 3. API 接続先を書き込んだ config.js
      const api = apiUrl.trim().replace(/\/$/, '')
      zip.file(
        'config.js',
        `// S3 用に自動生成。API の接続先を指定する\nwindow.__API_BASE_URL__ = ${JSON.stringify(api)};\n`,
      )

      // 4. 手順メモ
      zip.file(
        'README_S3.txt',
        [
          'このフォルダの中身をそのまま S3 バケットのルートにアップロードしてください。',
          '',
          '  aws s3 sync . s3://<バケット名> --delete',
          '',
          `API 接続先: ${api}`,
          '接続先を変えたい場合は config.js を書き換えるだけで済みます (再ビルド不要)。',
          'S3 側で「静的ウェブサイトホスティング」を有効にし、index と error の両方を index.html にしてください。',
          '',
        ].join('\n'),
      )

      const blob = await zip.generateAsync({ type: 'blob' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 's3-static-site.zip'
      a.click()
      URL.revokeObjectURL(a.href)
      setLog(`✅ ${files.length + 3} ファイルを zip にしました (API: ${api})`)
    } catch (e) {
      setLog(`❌ ${e.message || e}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="s3export">
      {open && (
        <div className="s3export-panel">
          <h3>S3 用の静的ファイルを出力</h3>
          <p>
            この画面の HTML / JS / CSS と、API の接続先を書いた <code>config.js</code> を
            zip にまとめます。解凍して中身を S3 バケットにアップロードしてください。
          </p>
          <label>
            API の接続先（EC2 の IP と 8000 番）
            <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
          </label>
          <button onClick={download} disabled={busy}>
            {busy ? '作成中...' : 'zip をダウンロード'}
          </button>
          {log && <p className="s3export-log">{log}</p>}
        </div>
      )}
      <button className="s3export-fab" onClick={() => setOpen((v) => !v)} title="S3 用ファイルを出力">
        {open ? '✕ 閉じる' : '📦 S3 用ファイルを出力'}
      </button>
    </div>
  )
}

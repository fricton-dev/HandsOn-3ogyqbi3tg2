import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ローカル開発時 (npm run dev) は /api を FastAPI へ中継する
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})

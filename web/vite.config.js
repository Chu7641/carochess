import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Khi phát triển: `npm run dev` (cổng 5173, mở cho cả mạng LAN), chuyển
// /api và /ws sang máy chủ Python ở cổng 8000 (`python -m server`).
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development and preview the browser talks to ONE origin (this server), which forwards
// API calls to the backend. That avoids CORS and keeps the backend address out of the code.
const backend = process.env.BACKEND_URL || 'http://localhost:8000'
const proxy = Object.fromEntries(
  ['/api', '/v1', '/health'].map((p) => [p, { target: backend, changeOrigin: true, timeout: 300000 }]),
)

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { sourcemap: false, chunkSizeWarningLimit: 700 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
  },
})

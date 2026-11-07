
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = process.env.BACKEND_URL || 'http://localhost:8000'

const proxy = Object.fromEntries(
  ['/api', '/v1', '/health'].map((path) => [
    path,
    {
      target: backend,
      changeOrigin: true,
      timeout: 300000,
    },
  ]),
)

export default defineConfig({
  plugins: [react()],

  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy,
  },

  preview: {
    host: '0.0.0.0',
    port: 4173,
    proxy,
  },

  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 700,
  },

  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
  },
})

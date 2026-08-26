/**
 * vite.config.js
 * Vite configuration for the Meeting Analyzer frontend.
 * - React plugin enabled
 * - Tailwind CSS v4 plugin enabled
 * - Dev server proxies /api requests to FastAPI (port 8000)
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

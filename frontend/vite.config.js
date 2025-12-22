import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'

// Backend URL - defaults to localhost for local development
// Can be overridden with BACKEND_URL environment variable
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const BACKEND_WS_URL = process.env.BACKEND_WS_URL || 'ws://localhost:8000'

// Check if SSL certificates exist (for HTTPS)
// Use absolute path to avoid __dirname issues in ES modules
const certPath = '/usr1/data/weiweis/chat_server/certs/server.crt'
const keyPath = '/usr1/data/weiweis/chat_server/certs/server.key'

// Control HTTPS via env var
// When ENABLE_HTTPS=false, Vite runs on HTTP only
// HTTPS is handled separately by start_dual_server.js on port 3443
const enableHttps = process.env.ENABLE_HTTPS === 'true'

const httpsConfig = (() => {
  if (enableHttps && fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    console.log('✅ SSL certificates found, enabling HTTPS')
    return {
      cert: fs.readFileSync(certPath),
      key: fs.readFileSync(keyPath)
    }
  }
  return false
})()

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    https: httpsConfig, // Enable HTTPS if certificates exist, otherwise HTTP
    allowedHosts: [
      'sf.lti.cs.cmu.edu',
      'localhost',
      '.cs.cmu.edu'
    ],
    proxy: {
      '/api': {
        // Backend URL - points to localhost:8000 for local development
        target: BACKEND_URL,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        // Backend WebSocket proxy - Vite will handle WebSocket upgrade automatically
        // Use HTTP URL for target, Vite handles ws:// upgrade
        target: BACKEND_URL,  // Use HTTP URL, not WebSocket URL
        ws: true,
        changeOrigin: true,
        secure: false,
        rewriteWsOrigin: true,
      }
    }
  }
})

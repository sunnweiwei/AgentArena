import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'

// Check if SSL certificates exist (for HTTPS)
// Use absolute path to avoid __dirname issues in ES modules
const certPath = '/usr1/data/weiweis/chat_server/certs/server.crt'
const keyPath = '/usr1/data/weiweis/chat_server/certs/server.key'

// Control HTTPS via env var (default true)
const enableHttps = process.env.ENABLE_HTTPS !== 'false'

const httpsConfig = (() => {
  if (enableHttps && fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    console.log('✅ SSL certificates found, enabling HTTPS')
    return {
      cert: fs.readFileSync(certPath),
      key: fs.readFileSync(keyPath)
    }
  }
  console.log('⚠️  Using HTTP only (HTTPS disabled)')
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
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      }
    }
  }
})

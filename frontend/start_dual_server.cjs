#!/usr/bin/env node
/**
 * Dual Protocol Server - HTTP on port 3000, HTTPS on port 3443
 * Starts Vite dev server on HTTP, then creates HTTPS proxy
 */

const { spawn } = require('child_process');
const https = require('https');
const http = require('http');
const httpProxy = require('http-proxy');
const fs = require('fs');
const path = require('path');

const HTTP_PORT = 3000;
const HTTPS_PORT = 3443;

const certPath = '/usr1/data/weiweis/chat_server/certs/server.crt';
const keyPath = '/usr1/data/weiweis/chat_server/certs/server.key';

// Check if certificates exist
const hasCert = fs.existsSync(certPath) && fs.existsSync(keyPath);
let sslOptions = null;

if (hasCert) {
  sslOptions = {
    cert: fs.readFileSync(certPath),
    key: fs.readFileSync(keyPath)
  };
  console.log('✅ SSL certificates found');
} else {
  console.log('⚠️  No SSL certificates found, HTTPS will not be available');
}

// Start Vite dev server on HTTP port 3000
console.log('🚀 Starting Vite dev server on HTTP port', HTTP_PORT);
const vite = spawn('npx', ['vite', '--port', HTTP_PORT, '--host', '0.0.0.0'], {
  stdio: 'inherit',
  shell: true,
  env: { ...process.env, ENABLE_HTTPS: 'false' }
});

vite.on('error', (err) => {
  console.error('Failed to start Vite:', err);
  process.exit(1);
});

// Wait a bit for Vite to start, then create HTTPS proxy
setTimeout(() => {
  if (hasCert && sslOptions) {
    console.log('🔒 Starting HTTPS proxy on port', HTTPS_PORT);
    
    const proxy = httpProxy.createProxyServer({
      target: `http://localhost:${HTTP_PORT}`,
      ws: true,
      changeOrigin: true
    });

    const httpsServer = https.createServer(sslOptions, (req, res) => {
      proxy.web(req, res);
    });

    // Handle WebSocket upgrades
    httpsServer.on('upgrade', (req, socket, head) => {
      proxy.ws(req, socket, head);
    });

    httpsServer.listen(HTTPS_PORT, '0.0.0.0', () => {
      console.log('');
      console.log('✅ Servers started successfully!');
      console.log(`   HTTP:  http://sf.lti.cs.cmu.edu:${HTTP_PORT}`);
      console.log(`   HTTPS: https://sf.lti.cs.cmu.edu:${HTTPS_PORT}`);
      console.log('');
    });

    httpsServer.on('error', (err) => {
      console.error('HTTPS server error:', err);
    });
  } else {
    console.log('');
    console.log('✅ HTTP server started!');
    console.log(`   HTTP:  http://sf.lti.cs.cmu.edu:${HTTP_PORT}`);
    console.log('   (HTTPS not available - no certificates found)');
    console.log('');
  }
}, 3000);

// Handle process termination
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down servers...');
  vite.kill();
  process.exit(0);
});

process.on('SIGTERM', () => {
  vite.kill();
  process.exit(0);
});


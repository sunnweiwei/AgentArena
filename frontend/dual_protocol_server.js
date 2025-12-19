#!/usr/bin/env node
/**
 * Dual Protocol Server - Supports both HTTP and HTTPS on port 3000
 * This proxies requests to the Vite dev server running on a different port
 */

const http = require('http');
const https = require('https');
const httpProxy = require('http-proxy-middleware');
const express = require('express');
const fs = require('fs');
const path = require('path');

const VITE_PORT = 3001; // Internal Vite server port
const PUBLIC_PORT = 3000; // Public port (both HTTP and HTTPS)

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
  console.log('✅ SSL certificates found, enabling HTTPS');
} else {
  console.log('⚠️  No SSL certificates found, HTTPS will not be available');
}

// Create Express app
const app = express();

// Proxy configuration
const proxyOptions = {
  target: `http://localhost:${VITE_PORT}`,
  changeOrigin: true,
  ws: true, // Enable WebSocket proxying
  logLevel: 'silent'
};

// Proxy all requests to Vite dev server
app.use('/', httpProxy.createProxyMiddleware(proxyOptions));

// Create HTTP server
const httpServer = http.createServer(app);
httpServer.listen(PUBLIC_PORT, '0.0.0.0', () => {
  console.log(`✅ HTTP server listening on http://0.0.0.0:${PUBLIC_PORT}`);
});

// Create HTTPS server if certificates exist
if (hasCert && sslOptions) {
  const httpsServer = https.createServer(sslOptions, app);
  httpsServer.listen(PUBLIC_PORT, '0.0.0.0', () => {
    console.log(`✅ HTTPS server listening on https://0.0.0.0:${PUBLIC_PORT}`);
  });
  
  // Handle WebSocket upgrades for HTTPS
  httpsServer.on('upgrade', (req, socket, head) => {
    proxyOptions.ws = true;
    const proxy = httpProxy.createProxyMiddleware(proxyOptions);
    proxy.upgrade(req, socket, head);
  });
}

// Handle WebSocket upgrades for HTTP
httpServer.on('upgrade', (req, socket, head) => {
  proxyOptions.ws = true;
  const proxy = httpProxy.createProxyMiddleware(proxyOptions);
  proxy.upgrade(req, socket, head);
});

console.log('');
console.log('🌐 Dual Protocol Server Started');
console.log(`   HTTP:  http://sf.lti.cs.cmu.edu:${PUBLIC_PORT}`);
if (hasCert) {
  console.log(`   HTTPS: https://sf.lti.cs.cmu.edu:${PUBLIC_PORT}`);
}
console.log(`   Proxying to Vite on port ${VITE_PORT}`);
console.log('');


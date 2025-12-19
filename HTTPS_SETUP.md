# HTTPS Setup Guide

## Current Issue

Your site uses a **self-signed certificate**, which causes browser security warnings. To fix this and make HTTPS easy to access, you need a trusted certificate from Let's Encrypt.

## Solution Options

### Option 1: Nginx Reverse Proxy (Recommended) ⭐

**Best for:** Production use, standard HTTPS port (443), no :3000 in URL

This sets up nginx to handle SSL termination and proxy to your frontend. Users access `https://sf.lti.cs.cmu.edu` (no port number).

**Setup:**
```bash
chmod +x setup_nginx_ssl.sh
./setup_nginx_ssl.sh
```

**Benefits:**
- ✅ Standard HTTPS port (443) - no :3000 needed
- ✅ Automatic certificate renewal
- ✅ Better performance (nginx handles SSL)
- ✅ Easy to add more services later

### Option 2: Direct Let's Encrypt Certificate

**Best for:** Keep current setup, just replace self-signed cert

This replaces your self-signed certificate with a Let's Encrypt one. Users still access `https://sf.lti.cs.cmu.edu:3000`.

**Setup:**
```bash
chmod +x setup_letsencrypt.sh
./setup_letsencrypt.sh
```

**Note:** This temporarily stops the frontend during certificate generation.

### Option 1: Let's Encrypt (Free, Trusted Certificate)

1. **Install certbot:**
   ```bash
   sudo apt update
   sudo apt install certbot python3-certbot-nginx -y
   ```

2. **Get certificate (standalone mode):**
   ```bash
   sudo certbot certonly --standalone -d sf.lti.cs.cmu.edu --email your-email@cmu.edu --agree-tos
   ```

3. **Copy certificates to your certs directory:**
   ```bash
   sudo cp /etc/letsencrypt/live/sf.lti.cs.cmu.edu/fullchain.pem /usr1/data/weiweis/chat_server/certs/server.crt
   sudo cp /etc/letsencrypt/live/sf.lti.cs.cmu.edu/privkey.pem /usr1/data/weiweis/chat_server/certs/server.key
   sudo chown weiweis:weiweis /usr1/data/weiweis/chat_server/certs/server.*
   ```

4. **Enable HTTPS:**
   ```bash
   export ENABLE_HTTPS=true
   # Then restart frontend
   ```

5. **Auto-renewal (optional):**
   ```bash
   # Add to crontab to auto-renew
   sudo crontab -e
   # Add: 0 0 * * * certbot renew --quiet && cp /etc/letsencrypt/live/sf.lti.cs.cmu.edu/fullchain.pem /usr1/data/weiweis/chat_server/certs/server.crt && cp /etc/letsencrypt/live/sf.lti.cs.cmu.edu/privkey.pem /usr1/data/weiweis/chat_server/certs/server.key && chown weiweis:weiweis /usr1/data/weiweis/chat_server/certs/server.*
   ```

### Option 2: Use CMU Institutional Certificate

If CMU provides SSL certificates for `sf.lti.cs.cmu.edu`, you can use those instead:
1. Obtain the certificate and key from CMU IT
2. Place them in `/usr1/data/weiweis/chat_server/certs/` as `server.crt` and `server.key`
3. Set `ENABLE_HTTPS=true` and restart

## Switching Between HTTP and HTTPS

- **Use HTTP (default)**: `export ENABLE_HTTPS=false` or don't set it
- **Use HTTPS**: `export ENABLE_HTTPS=true`

Then restart the frontend service.


# Dual Protocol Setup (HTTP + HTTPS)

This setup allows users to access your site via both HTTP and HTTPS on different ports.

## Ports

- **HTTP**: Port 3000 - `http://sf.lti.cs.cmu.edu:3000` (no certificate warnings)
- **HTTPS**: Port 3443 - `https://sf.lti.cs.cmu.edu:3443` (with trusted certificate)

## Setup Steps

### 1. Get Let's Encrypt Certificate (Optional but Recommended)

To get a trusted certificate for HTTPS (no browser warnings):

```bash
cd /usr1/data/weiweis/chat_server
./setup_letsencrypt_direct.sh
```

This will:
- Temporarily stop the frontend
- Get a Let's Encrypt certificate
- Replace the self-signed certificate
- Restart the frontend

**Note:** This requires sudo access and will temporarily stop your frontend for ~30 seconds.

### 2. Install Dependencies

```bash
cd /usr1/data/weiweis/chat_server/frontend
source ~/.nvm/nvm.sh
npm install
```

This installs `http-proxy` which is needed for the dual protocol server.

### 3. Start the Dual Protocol Server

```bash
cd /usr1/data/weiweis/chat_server/frontend
source ~/.nvm/nvm.sh
npm run dev:dual
```

This will:
- Start Vite dev server on HTTP port 3000
- Start HTTPS proxy on port 3443 (if certificates exist)

### 4. Access Your Site

- **HTTP**: `http://sf.lti.cs.cmu.edu:3000` - Easy access, no warnings
- **HTTPS**: `https://sf.lti.cs.cmu.edu:3443` - Secure, trusted certificate

## Updating Startup Scripts

To use the dual protocol server in your startup scripts, update `start_services.sh`:

```bash
# In start_frontend() function, change:
npm run dev
# To:
npm run dev:dual
```

## Certificate Auto-Renewal

Let's Encrypt certificates expire after 90 days. To auto-renew:

```bash
crontab -e
# Add this line:
0 0 * * * sudo certbot renew --quiet && sudo cp /etc/letsencrypt/live/sf.lti.cs.cmu.edu/fullchain.pem /usr1/data/weiweis/chat_server/certs/server.crt && sudo cp /etc/letsencrypt/live/sf.lti.cs.cmu.edu/privkey.pem /usr1/data/weiweis/chat_server/certs/server.key && sudo chown weiweis:weiweis /usr1/data/weiweis/chat_server/certs/server.*
```

This will renew the certificate daily (it only actually renews when needed, within 30 days of expiration).


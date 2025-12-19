#!/bin/bash
# Setup Let's Encrypt certificate for direct use with Vite (port 3000)
# This replaces the self-signed certificate with a trusted one

set -e

DOMAIN="sf.lti.cs.cmu.edu"
EMAIL="weiweis@cs.cmu.edu"  # Update with your email
CERT_DIR="/usr1/data/weiweis/chat_server/certs"

echo "=== Setting up Let's Encrypt Certificate for Port 3000 ==="
echo "Domain: $DOMAIN"
echo ""

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    sudo apt update
    sudo apt install -y certbot
fi

# Stop frontend temporarily (certbot needs port 80 for verification)
echo "Stopping frontend service temporarily for certificate generation..."
echo "This will take about 30 seconds..."
pkill -f "node.*vite" || true
sleep 2

# Make sure port 80 is available (stop any service using it)
sudo systemctl stop nginx 2>/dev/null || true
sleep 1

# Get certificate using standalone mode
echo "Requesting certificate from Let's Encrypt..."
sudo certbot certonly --standalone \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    --preferred-challenges http

# Copy certificates to our certs directory
echo "Copying certificates..."
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$CERT_DIR/server.crt"
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$CERT_DIR/server.key"
sudo chown weiweis:weiweis "$CERT_DIR/server.crt" "$CERT_DIR/server.key"
sudo chmod 644 "$CERT_DIR/server.crt"
sudo chmod 600 "$CERT_DIR/server.key"

echo ""
echo "✅ Certificate installed successfully!"
echo ""
echo "Certificates are now in: $CERT_DIR"
echo "Your site will use HTTPS with a trusted certificate!"
echo ""
echo "Access your site at:"
echo "  HTTP:  http://$DOMAIN:3000 (no warnings)"
echo "  HTTPS: https://$DOMAIN:3443 (trusted certificate, no warnings)"
echo ""
echo "To auto-renew certificates, add to crontab:"
echo "  crontab -e"
echo "  Add: 0 0 * * * sudo certbot renew --quiet && sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/server.crt && sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/server.key && sudo chown weiweis:weiweis $CERT_DIR/server.*"
echo ""
echo "Now restart your frontend service to use the new certificate."
echo "Use: npm run dev:dual (in frontend directory) to start both HTTP and HTTPS servers."


#!/bin/bash
# Setup Let's Encrypt SSL certificate for sf.lti.cs.cmu.edu

set -e

CERT_DIR="/usr1/data/weiweis/chat_server/certs"
DOMAIN="sf.lti.cs.cmu.edu"
EMAIL="weiweis@cs.cmu.edu"  # Update with your email

echo "=== Setting up Let's Encrypt SSL Certificate ==="
echo "Domain: $DOMAIN"
echo ""

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    sudo apt update
    sudo apt install -y certbot
fi

# Stop frontend temporarily (certbot needs port 80)
echo "Stopping frontend service temporarily for certificate generation..."
pkill -f "node.*vite" || true
sleep 2

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
echo "Restart your frontend service to use the new certificate."
echo ""
echo "To auto-renew certificates, add to crontab:"
echo "sudo crontab -e"
echo "Add: 0 0 * * * certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem $CERT_DIR/server.crt && cp /etc/letsencrypt/live/$DOMAIN/privkey.pem $CERT_DIR/server.key && chown weiweis:weiweis $CERT_DIR/server.*"


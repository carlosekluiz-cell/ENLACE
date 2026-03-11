#!/bin/bash
# Pulso go-live script — run as root: sudo bash /home/dev/enlace/go-live.sh
set -e

echo "=== Step 1: SSL Certificates ==="
certbot certonly --webroot -w /home/dev/www/pulso.network \
  -d pulso.network \
  -d www.pulso.network \
  -d app.pulso.network \
  -d api.pulso.network \
  --non-interactive --agree-tos --email admin@pulso.network

echo "=== Step 2: Production nginx config ==="
cp /home/dev/enlace/pulso-nginx.conf /etc/nginx/sites-available/pulso
nginx -t && nginx -s reload

echo "=== Step 3: Frontend API URL ==="
echo 'NEXT_PUBLIC_API_URL=https://api.pulso.network' > /home/dev/enlace/frontend/.env.local
chown dev:dev /home/dev/enlace/frontend/.env.local

echo "=== Step 4: Kill old servers ==="
pkill -f "uvicorn python.api.main" || true
pkill -f "next-server" || true
pkill -f "node.*next.*4100" || true
sleep 2

echo "=== Step 5: Start API ==="
cd /home/dev/enlace
su - dev -c "cd /home/dev/enlace && nohup python3 -m uvicorn python.api.main:app --host 0.0.0.0 --port 8000 > /tmp/pulso-api.log 2>&1 &"
sleep 3

echo "=== Step 6: Build and start frontend ==="
su - dev -c "cd /home/dev/enlace/frontend && npm run build && nohup npm start -- -p 4100 > /tmp/pulso-frontend.log 2>&1 &"
sleep 5

echo ""
echo "=== DONE ==="
echo "  Site:     https://pulso.network"
echo "  App:      https://app.pulso.network"
echo "  API:      https://api.pulso.network/health"
echo ""
echo "Testing..."
curl -s -o /dev/null -w "  API health: %{http_code}\n" http://localhost:8000/health
curl -s -o /dev/null -w "  Frontend:   %{http_code}\n" http://localhost:4100
echo "LIVE!"

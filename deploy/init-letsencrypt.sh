#!/usr/bin/env bash
# One-shot helper: issue a real Let's Encrypt certificate for $DOMAIN
# the first time the stack is brought up on a new host.
#
# Usage:
#   1. Ensure DNS for $DOMAIN already points to this VPS.
#   2. cd /opt/pengelola-keuangan && bash deploy/init-letsencrypt.sh
#
# It expects DOMAIN and LETSENCRYPT_EMAIL to be set in .env.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "❌ .env tidak ada. copy .env.example dan isi DOMAIN + LETSENCRYPT_EMAIL." >&2
  exit 1
fi

# shellcheck source=/dev/null
set -a; source .env; set +a

: "${DOMAIN:?DOMAIN belum di-set di .env}"
: "${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL belum di-set di .env}"

echo "→ Domain: $DOMAIN"
echo "→ Email: $LETSENCRYPT_EMAIL"

# 1. Bring up nginx with the bootstrap HTTP-only config so ACME challenges work.
echo "→ Starting nginx in bootstrap mode (HTTP only)…"
NGINX_TEMPLATE=bootstrap docker compose up -d --build nginx web api db

# Wait for nginx to be reachable
echo "→ Waiting 5s for nginx to settle…"
sleep 5

# 2. Run certbot to obtain a real certificate using webroot challenge.
echo "→ Requesting Let's Encrypt certificate via webroot…"
docker compose run --rm --entrypoint sh certbot -c "
  certbot certonly \
    --webroot --webroot-path=/var/www/certbot \
    --email '$LETSENCRYPT_EMAIL' \
    --agree-tos --no-eff-email \
    --keep-until-expiring \
    -d '$DOMAIN'
"

# 3. Switch nginx to the full HTTPS config and reload.
echo "→ Switching nginx to HTTPS config…"
docker compose stop nginx
docker compose up -d nginx

echo "✅ Selesai. Buka https://$DOMAIN"

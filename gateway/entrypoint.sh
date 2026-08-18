#!/bin/sh
# ============================================================
# 99-gen-certs.sh — generate self-signed fallback TLS certs.
# Runs as an nginx docker-entrypoint.d hook (before nginx starts).
# Real certs mounted over /etc/nginx/certs take precedence.
# ============================================================

set -eu

FULLCHAIN=/etc/nginx/certs/fullchain.pem
PRIVKEY=/etc/nginx/certs/privkey.pem

if [ -s "$FULLCHAIN" ] && [ -s "$PRIVKEY" ]; then
    echo "[gen-certs] Existing certificates found, skipping generation."
    exit 0
fi

echo "[gen-certs] Certificate files empty or missing, generating self-signed certs..."

if ! command -v openssl >/dev/null 2>&1; then
    echo "[gen-certs] openssl not installed; installing..."
    apk add --no-cache openssl >/dev/null 2>&1
fi

openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "$PRIVKEY" \
    -out "$FULLCHAIN" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:app.yourapp.com,IP:127.0.0.1" >/dev/null 2>&1

echo "[gen-certs] Self-signed certificates generated."

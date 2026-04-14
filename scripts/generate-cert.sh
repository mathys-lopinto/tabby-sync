#!/usr/bin/env bash
#
# Generate a self-signed TLS certificate (ECDSA P-256) for the nginx
# reverse proxy. Reads DOMAIN from .env unless given as $1.
#
# 825 days is the max validity accepted by iOS/macOS/Chrome for
# user-imported certs.
#
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
repo_root=$(cd -- "${script_dir}/.." &>/dev/null && pwd)

domain=${1:-}
if [[ -z "${domain}" ]]; then
    if [[ -f "${repo_root}/.env" ]]; then
        domain=$(grep -E '^DOMAIN=' "${repo_root}/.env" | head -1 | cut -d= -f2- | tr -d '"')
    fi
fi

if [[ -z "${domain}" ]]; then
    echo "error: no domain given and DOMAIN not set in .env" >&2
    echo "usage: $0 [domain]" >&2
    exit 1
fi

ssl_dir="${repo_root}/caddy/ssl"
mkdir -p "${ssl_dir}"

cert_path="${ssl_dir}/fullchain.pem"
key_path="${ssl_dir}/privkey.pem"

echo "Generating self-signed certificate for: ${domain}"
echo "  -> ${cert_path}"
echo "  -> ${key_path}"

openssl req \
    -x509 \
    -nodes \
    -newkey ec \
    -pkeyopt ec_paramgen_curve:P-256 \
    -days 825 \
    -keyout "${key_path}" \
    -out "${cert_path}" \
    -subj "/CN=${domain}" \
    -addext "subjectAltName=DNS:${domain}" \
    -addext "keyUsage=digitalSignature" \
    -addext "extendedKeyUsage=serverAuth"

chmod 600 "${key_path}"
chmod 644 "${cert_path}"

echo
echo "Done. Restart caddy to pick up the new certificate:"
echo "  docker compose -f docker-compose.yml -f docker-compose.https.yml restart caddy"

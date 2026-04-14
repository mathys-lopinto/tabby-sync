# tabby-sync

A minimal, self-hostable backend for the **config sync** feature of the [Tabby terminal](https://tabby.sh).

This is a stripped-down fork of [tabby-web](https://github.com/Eugeny/tabby-web) that keeps only the endpoints the Tabby desktop client calls to push and pull its `config.yaml`. Everything else that made tabby-web a full web terminal and gateway has been removed.

## Why this fork

Upstream `tabby-web` bundles a lot of features that most self-hosters do not need for config sync alone: an Angular web terminal, a WebSocket gateway proxy for SSH/Telnet, OAuth social auth with seven providers, GitHub Sponsors integration, Tabby version distribution, analytics.

If you only want your `config.yaml` synced between your machines, you end up running, patching, and monitoring all of it anyway.

`tabby-sync` keeps the backend at about 330 lines of real Python (ignoring migrations) with eight production dependencies. Small enough to read end-to-end in an afternoon and small enough that you can personally own every CVE advisory against it.

## Scope

**In scope**

- Store a user's Tabby config on the server.
- Allow the Tabby desktop client to pull and push it.
- Authenticate the client via a static Bearer token.
- Serve multiple configs per user with an `active` pointer.

**Out of scope**

- No web terminal, no browser UI. Tabby desktop is the only client.
- No OAuth, no social login, no sign-up page. Users are created in Django admin.
- No connection gateway for SSH/Telnet. Run one separately if you need it ([`tabby-connection-gateway`](https://github.com/Eugeny/tabby-connection-gateway)).
- No Tabby app version distribution, no sponsors check, no analytics.
- No TLS termination. Put a reverse proxy (Caddy, Traefik, nginx) in front.

## Stack

- Python 3.14, Django 6, Django REST Framework
- Postgres 18 by default (SQLite and MySQL/MariaDB also supported)
- Gunicorn, WhiteNoise
- Containerized with a multi-stage Dockerfile on `python:3.14-slim`

## Requirements

### Software

- Python 3.14+ for local development.
- Poetry 2.x for dependency management.
- Docker and Docker Compose for the containerized deployment.
- Any database supported by Django: Postgres, MySQL/MariaDB, SQLite.

### System

This fork carries none of the upstream frontend build, so resource needs are modest.

| Resource | Build | Runtime |
|---|---|---|
| CPU | 1 core | 1 core |
| RAM | 512 MB | 256 MB |
| Disk | 2 GB | 500 MB + database |

## Architecture

```
Tabby desktop
  |  Authorization: Bearer <config_sync_token>
  v
Reverse proxy (you provide)     <-- TLS, rate limit
  |
  v
Gunicorn (4 workers by default)
  |
  v
Django + DRF
  |-- TokenMiddleware           <-- matches Bearer to User.config_sync_token
  +-- ViewSets                  <-- /api/1/configs, /api/1/user
  |
  v
Postgres / MySQL / SQLite
```

## API

| Method | Route | Auth | Purpose |
|---|---|---|---|
| `GET`, `PUT` | `/api/1/user` | Bearer | Profile of the current user |
| `GET`, `POST` | `/api/1/configs` | Bearer | List / create configs |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/1/configs/<id>` | Bearer | CRUD one config |
| any | `/admin/` | session | Django admin |

The Bearer value is the `config_sync_token` field on `User`, auto-generated on user creation (64 bytes, hex-encoded).

## Running it

### Production (Docker)

```bash
cp .env.example .env
sed -i "s/change-me-please/$(openssl rand -hex 24)/" .env
sed -i "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$(openssl rand -hex 32)/" .env

docker compose up -d
docker compose exec tabby /app/manage.sh createsuperuser
```

The backend listens on `http://localhost:9090`. The admin is served at `/admin/`.

### Local development

The `manage.sh` wrapper is meant for the container (paths under `/app` and `/venv`). For host development, call Django through Poetry directly:

```bash
cd backend
poetry install                  # Postgres driver installed by default
# For MariaDB/MySQL instead:
# poetry install --extras mysql

cat > .env <<EOF
DATABASE_URL=sqlite:///$(pwd)/dev.db
DJANGO_SECRET_KEY=dev-not-secret
DEBUG=True
EOF

poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py runserver
```

The dev server listens on `http://127.0.0.1:8000`.

Lint and format with Ruff:

```bash
poetry run ruff check .
poetry run ruff format .
```

### Creating a sync user

Every client gets its own user. Sync tokens are stored hashed in the database and never returned by the API, so the cleartext can only be retrieved at the moment of creation or rotation.

1. Open `/admin/` and sign in with the superuser created above.
2. Go to **Users** and click **Add user**.
   - Set a username.
   - Set **Password-based authentication** to **Disabled** (the account only uses its Bearer token).
3. Save. The admin redirects to a dedicated page that displays the newly-issued sync token in a read-only field. Click **Copy** and keep it somewhere safe.
4. In Tabby desktop, go to **Settings** then **Config sync** and paste:
   - **Server:** your deployment URL (e.g. `http://localhost:9090` for a local Docker stack, or your HTTPS domain in prod).
   - **Token:** the value copied above.

If you missed the token or lost it, open the user's edit page and click **Regenerate sync token**. A new token is issued, the old one is invalidated and Tabby desktop on the old machine will need to be reconfigured with the new value.

Never grant `is_staff` or `is_superuser` to a sync-only user. Keep the admin privileges on a separate account.

## Database selection

The backend is database-agnostic. Set `DATABASE_URL` accordingly:

```env
# SQLite (no driver needed)
DATABASE_URL=sqlite:////absolute/path/to/dev.db

# Postgres (driver installed by default)
DATABASE_URL=postgres://tabby:pass@host:5432/tabby

# MySQL / MariaDB (requires the mysql extra)
DATABASE_URL=mysql://tabby:pass@host:3306/tabby
```

## HTTPS via Caddy

An optional Caddy reverse-proxy stack is shipped as a compose overlay. It terminates TLS, handles HTTP/3, and only proxies `/api/*`, `/admin/*` and `/static/*` to the backend. Everything else is answered with a plain 404 so the Django instance is not exposed beyond those three paths.

By default Caddy obtains a Let's Encrypt certificate over ACME on first boot. This requires the domain set in `$DOMAIN` to resolve publicly to the host and port 80 to be reachable from the Internet for the HTTP-01 challenge. Set `$ACME_EMAIL` in `.env` so Let's Encrypt can send recovery and expiry notices.

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

### Self-signed mode (LAN / VPN deployments)

If the host is not reachable from the Internet (LAN, VPN, homelab), ACME cannot complete. In that case, generate a self-signed certificate and tell Caddy to use it instead of requesting one from Let's Encrypt. In `caddy/Caddyfile`, uncomment the `tls /etc/caddy/ssl/fullchain.pem /etc/caddy/ssl/privkey.pem` line, then run:

```bash
./scripts/generate-cert.sh
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d
```

Every client will raise a trust warning until the certificate is imported into its trust store by hand.

### What this stack does not include

The stack ships with secure TLS settings and standard hardening headers, but it does not include rate limiting at the proxy level, a web application firewall, or fail2ban-style IP banning. The Django admin login is reachable on the same hostname as the API, which makes it a natural brute-force target if the instance is exposed publicly. For hostile environments, put another gateway in front (Cloudflare Tunnel, a managed load balancer, or a harder Caddy config with rate limiting) and keep the tabby-sync instance itself on an internal network.

### Known CVEs against `caddy:2.11.2-alpine`

A Trivy scan of the pinned image reports several CVEs, but only two are reachable through our usage of Caddy (reverse proxy with a static self-signed certificate, no ACME, no file serving, no gRPC, no OpenTelemetry). Both are denial-of-service or parsing bugs, not remote code execution or authentication bypass.

- **CVE-2026-32283** (Go stdlib `crypto/tls`, severity UNKNOWN). Multiple TLS 1.3 `KeyUpdate` messages from a client can cause a denial of service on the TLS server. Caddy terminates TLS on our behalf, so an attacker able to open a TLS handshake could trigger it. Fixed in Go 1.25.9 and 1.26.2; will land in a later Caddy release.
- **CVE-2026-25679** (Go stdlib `net/url`, severity HIGH). Incorrect parsing of IPv6 host literals. Only reachable when a request Host header contains an IPv6 literal and our configuration matches on it, which is not the usual case for a LAN deployment. Fixed in Go 1.25.8 and 1.26.1.

All the other findings (ACME, smallstep, go-jose, gRPC, OpenTelemetry, OpenSSL CMS, x509 chain verification, `archive/tar`, `html/template`, zlib) sit on code paths we do not exercise and are therefore not exploitable against this stack. They will still be resolved over time as we bump the base image.

## Security notes

The application does not terminate TLS on its own. CSRF and session cookies are only marked `Secure` when a recognized HTTPS `FRONTEND_URL` is configured in the environment.

The `config_sync_token` is a bearer secret. Anyone holding it can read and overwrite the user's Tabby configuration, so it should be treated as a password and rotated if it is ever exposed.

The backend performs no rate limiting. If the instance is exposed beyond a trusted network, rate limiting belongs on the upstream reverse proxy or WAF.

The Django admin is the only supported way to provision users. On a self-hosted deployment it should live behind an IP allowlist or a VPN whenever possible, and sync-only users should never be granted `is_staff` or `is_superuser`.

## Credits

This project is a fork of [`tabby-web`](https://github.com/Eugeny/tabby-web) by [Eugeny](https://github.com/Eugeny), distributed under the MIT license. The original copyright notice is preserved in [`LICENSE`](LICENSE).

## License

MIT. See [`LICENSE`](LICENSE).

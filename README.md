# tabby-sync

[![CI](https://github.com/mathys-lopinto/tabby-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/mathys-lopinto/tabby-sync/actions/workflows/ci.yml)
[![codecov](https://codecov.io/github/mathys-lopinto/tabby-sync/graph/badge.svg?token=UE1MPY4ACU)](https://codecov.io/github/mathys-lopinto/tabby-sync)
[![Release](https://img.shields.io/github/v/release/mathys-lopinto/tabby-sync?sort=semver)](https://github.com/mathys-lopinto/tabby-sync/releases)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A minimal, self-hostable backend for the **config sync** feature of the [Tabby terminal](https://tabby.sh).

This is a stripped-down fork of [tabby-web](https://github.com/Eugeny/tabby-web) that keeps only the endpoints the Tabby desktop client calls to push and pull its `config.yaml`. Everything else that made tabby-web a full web terminal and gateway has been removed.

## Quick start

```bash
git clone https://github.com/mathys-lopinto/tabby-sync.git && cd tabby-sync
cp .env.example .env
sed -i "s/change-me-please/$(openssl rand -hex 24)/" .env
sed -i "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$(openssl rand -hex 32)/" .env
sed -i "s/^DOMAIN=.*/DOMAIN=sync.yourdomain.com/" .env
sed -i "s/^ACME_EMAIL=.*/ACME_EMAIL=you@yourdomain.com/" .env

docker compose up -d
docker compose exec tabby /app/manage.sh createsuperuser
```

Open `https://sync.yourdomain.com/admin/`, create a sync user, copy the token from the dedicated display page, paste it into **Tabby desktop > Settings > Config sync**.

## Why this fork

Upstream `tabby-web` bundles a lot of features that most self-hosters do not need for config sync alone: an Angular web terminal, a WebSocket gateway proxy for SSH/Telnet, OAuth social auth with seven providers, GitHub Sponsors integration, Tabby version distribution, analytics.

If you only want your `config.yaml` synced between your machines, you end up running, patching, and monitoring all of it anyway.

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

## Stack

- Python 3.14, Django 6, Django REST Framework
- Postgres 18 by default (SQLite and MySQL/MariaDB also supported)
- Caddy 2 as reverse proxy (ACME / Let's Encrypt by default, self-signed for LAN)
- Gunicorn, WhiteNoise
- Containerized with a multi-stage Dockerfile on `python:3.14-slim`

## Requirements

### Software

- Docker and Docker Compose for the default deployment.
- A public domain pointing to the host (for Let's Encrypt). For LAN/VPN setups, a self-signed certificate works too.
- Python 3.14+ and Poetry 2.x only if you develop locally outside Docker.

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
Caddy (TLS, ACME, HTTP/3)
  |  /api/*, /admin/*, /static/* only
  v
Gunicorn (4 workers by default)
  |
  v
Django + DRF
  |-- TokenMiddleware           <-- matches Bearer hash to User
  +-- ViewSets                  <-- /api/1/configs, /api/1/user
  |
  v
Postgres / MySQL / SQLite
```

## API

| Method | Route | Auth | Purpose |
|---|---|---|---|
| `GET`, `PUT`, `PATCH` | `/api/1/user` | Bearer | Profile of the current user |
| `GET`, `POST` | `/api/1/configs` | Bearer | List / create configs |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/1/configs/<id>` | Bearer | CRUD one config |
| `GET` | `/api/health` | none | Health check for probes |
| any | `/admin/` | session | Django admin |

The Bearer value is the `config_sync_token`, auto-generated on user creation (64 bytes, hex-encoded, stored as a SHA-256 hash). It is shown exactly once at creation or on explicit rotation.

## Deployment

### Production (default)

The default `docker-compose.yml` runs three services: `tabby` (Django/gunicorn), `db` (Postgres) and `caddy` (reverse proxy with TLS). The backend is never exposed directly; only Caddy listens on ports 80 and 443.

```bash
cp .env.example .env
# Fill in DB_PASSWORD, DJANGO_SECRET_KEY, DOMAIN and ACME_EMAIL
docker compose up -d
docker compose exec tabby /app/manage.sh createsuperuser
```

By default the compose file pulls the published image from `ghcr.io/mathys-lopinto/tabby-sync:latest`. To build locally instead, swap the `image:` and `build:` comments in `docker-compose.yml`.

A plain-text `/api/health` endpoint returns `ok` with no authentication required, suitable for uptime probes.

### Self-signed mode (LAN / VPN)

If the host is not reachable from the Internet, ACME cannot complete. In that case, uncomment the `tls` line in `caddy/Caddyfile` (instructions are in the file) and generate a self-signed certificate:

```bash
./scripts/generate-cert.sh
docker compose up -d
```

Every client will raise a trust warning until the certificate is imported into its trust store. On the host running Tabby desktop, add `caddy/ssl/fullchain.pem` to the system's trusted CA store (e.g. `sudo cp fullchain.pem /usr/local/share/ca-certificates/tabby-sync.crt && sudo update-ca-certificates` on Debian/Ubuntu, or import it via Keychain Access on macOS, or the certificate manager on Windows).

### Local development (without Docker)

A development overlay disables Caddy and exposes the backend directly on port 9090:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Or without Docker at all:

```bash
cd backend
poetry install
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

## Creating a sync user

Every client gets its own user. Sync tokens are stored hashed in the database and never returned by the API, so the cleartext can only be retrieved at the moment of creation or rotation.

1. Open `/admin/` and sign in with the superuser created above.
2. Go to **Users** and click **Add user**.
   - Set a username.
   - Set **Password-based authentication** to **Disabled** (the account only uses its Bearer token).
3. Save. The admin redirects to a dedicated page that displays the newly-issued sync token in a read-only field. Click **Copy** and keep it somewhere safe.
4. In Tabby desktop, go to **Settings** then **Config sync** and paste:
   - **Server:** your deployment URL (e.g. `https://sync.yourdomain.com`).
   - **Token:** the value copied above.

If you missed the token or lost it, open the user's edit page and click **Regenerate sync token**. A new token is issued, the old one is invalidated and Tabby desktop will need to be reconfigured with the new value.

Never grant `is_staff` or `is_superuser` to a sync-only user. Keep the admin privileges on a separate account.

### Scripted provisioning

Two management commands are available for automation. Both print the cleartext token on `stdout` and the status message on `stderr`, so the token can be piped directly into another tool:

```bash
TOKEN=$(docker compose exec -T tabby /app/manage.sh create_sync_user alice)
TOKEN=$(docker compose exec -T tabby /app/manage.sh refresh_token alice)
```

`create_sync_user` sets an unusable password, so the new account cannot be used to log into the admin. Use `createsuperuser` for admin accounts.

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

## Security notes

Sync tokens are stored as SHA-256 hashes. The cleartext is surfaced exactly once at creation or on rotation through the admin UI or the `create_sync_user` / `refresh_token` CLI commands. A database dump does not expose usable tokens.

The `config_sync_token` is a bearer secret. Anyone holding it can read and overwrite the user's Tabby configuration, so it should be treated as a password and rotated if it is ever exposed.

The default deployment forces all traffic through Caddy with TLS. The backend container has no published ports and is not directly reachable from outside the Docker network. Secure cookie flags are enabled by default.

The Django admin is the only supported way to provision users through a browser. Sync-only users should never be granted `is_staff` or `is_superuser`.

## Automation

A GitHub Actions CI workflow runs Ruff lint, Ruff format check, and the full pytest suite with coverage gate on every push and pull request. Coverage reports are uploaded to Codecov for the badge above.

A separate release workflow builds and publishes a multi-tagged Docker image to `ghcr.io/mathys-lopinto/tabby-sync` whenever a `v*.*.*` git tag is pushed. Stable tags move `:latest`; any pre-release tag (`alpha`/`beta`/`rc`) keeps its own tag only.

Dependabot watches the Poetry, Docker and GitHub Actions ecosystems and opens grouped pull requests for dependency updates.

## Credits

This project is a fork of [`tabby-web`](https://github.com/Eugeny/tabby-web) by [Eugeny](https://github.com/Eugeny), distributed under the MIT license. The original copyright notice is preserved in [`LICENSE`](LICENSE).

## License

MIT. See [`LICENSE`](LICENSE).

# tabby-sync

A minimal, self-hostable backend for the **config sync** feature of the
[Tabby terminal](https://tabby.sh).

This is a stripped-down fork of [tabby-web](https://github.com/Eugeny/tabby-web)
that keeps only the endpoints the Tabby desktop client calls to push and
pull its `config.yaml`. Everything else that made tabby-web a full web
terminal and gateway has been removed.

## Why this fork

Upstream `tabby-web` bundles a lot of features that most self-hosters do
not need for config sync alone: an Angular web terminal, a WebSocket
gateway proxy for SSH/Telnet, OAuth social auth with seven providers,
GitHub Sponsors integration, Tabby version distribution, analytics.

If you only want your `config.yaml` synced between your machines, you end
up running, patching, and monitoring all of it anyway.

`tabby-sync` keeps the backend at about 300 lines of real Python
(ignoring migrations) with eight production dependencies. Small enough
to read end-to-end in an afternoon and small enough that you can
personally own every CVE advisory against it.

## Scope

**In scope**

- Store a user's Tabby config on the server.
- Allow the Tabby desktop client to pull and push it.
- Authenticate the client via a static Bearer token.
- Serve multiple configs per user with an `active` pointer.

**Out of scope**

- No web terminal, no browser UI. Tabby desktop is the only client.
- No OAuth, no social login, no sign-up page. Users are created in
  Django admin.
- No connection gateway for SSH/Telnet. Run one separately if you need
  it ([`tabby-connection-gateway`](https://github.com/Eugeny/tabby-connection-gateway)).
- No Tabby app version distribution, no sponsors check, no analytics.
- No TLS termination. Put a reverse proxy (Caddy, Traefik, nginx) in
  front.

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

This fork carries none of the upstream frontend build, so resource
needs are modest.

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

The Bearer value is the `config_sync_token` field on `User`,
auto-generated on user creation (64 bytes, hex-encoded).

## Local development

```bash
cd backend
poetry install                  # Postgres driver installed by default
# For MariaDB/MySQL instead:
# poetry install --extras mysql

export DATABASE_URL=sqlite:////tmp/dev.db
export DJANGO_SECRET_KEY=dev-not-secret
./manage.sh migrate
./manage.sh createsuperuser
./manage.sh runserver
```

Lint and format with Ruff:

```bash
poetry run ruff check .
poetry run ruff format .
```

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

- The app has no TLS of its own. CSRF and session cookies are only
  marked `Secure` when a recognized HTTPS `FRONTEND_URL` is configured.
- `config_sync_token` is a bearer secret. Anyone holding it can read
  and overwrite the user's Tabby config. Treat it like a password.
- The app performs no rate limiting. Put one at the reverse proxy if
  the instance is exposed publicly.
- The admin site is the only way to provision users. Protect it behind
  an allowlist or VPN where possible.

## Credits

This project is a fork of [`tabby-web`](https://github.com/Eugeny/tabby-web)
by [Eugeny](https://github.com/Eugeny), distributed under the MIT license.
The original copyright notice is preserved in [`LICENSE`](LICENSE).

## License

MIT. See [`LICENSE`](LICENSE).

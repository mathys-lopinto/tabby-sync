import sys

import pytest


def reload_settings(monkeypatch, **env):
    # Neutralize the .env file so tests aren't polluted by what's on disk.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    # Drop the cached module so conditionally-defined attributes from
    # a previous test don't leak into this one.
    sys.modules.pop("tabby.settings", None)
    import tabby.settings as s

    return s


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("True", True),
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("False", False),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("anything-else", False),
    ],
)
def test_debug_parsing(monkeypatch, value, expected):
    s = reload_settings(
        monkeypatch,
        DEBUG=value,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
    )
    assert s.DEBUG is expected


def test_debug_default_is_false(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DEBUG=None,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
    )
    assert s.DEBUG is False


def test_secret_key_falls_back_to_insecure_default(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY=None,
        DEBUG="False",
        DATABASE_URL="sqlite:///:memory:",
    )
    assert s.SECRET_KEY == "django-insecure"


def test_secure_proxy_ssl_header_is_set(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
    )
    # Required so request.is_secure() trusts the X-Forwarded-Proto
    # header set by Caddy.
    assert s.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_csrf_cookie_secure_when_https_frontend(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
        FRONTEND_URL="https://sync.example.com",
    )
    assert getattr(s, "CSRF_COOKIE_SECURE", False) is True
    assert getattr(s, "SESSION_COOKIE_SECURE", False) is True


def test_no_secure_cookie_flags_without_frontend_url(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
        FRONTEND_URL=None,
        CORS_EXTRA_URL=None,
    )
    # No HTTPS frontend declared, so secure cookies are not forced.
    assert getattr(s, "CSRF_COOKIE_SECURE", False) is False


def test_cors_origins_include_frontend_and_extra(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
        FRONTEND_URL="https://sync.example.com",
    )
    assert "https://sync.example.com" in s.CORS_ALLOWED_ORIGINS

    s2 = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
        CORS_EXTRA_URL="https://other.example.com",
    )
    assert "https://other.example.com" in s2.CORS_ALLOWED_ORIGINS


def test_token_middleware_is_active(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
    )
    assert "tabby.middleware.TokenMiddleware" in s.MIDDLEWARE


def test_only_json_renderer_is_configured(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
    )
    renderers = s.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]
    assert renderers == ("rest_framework.renderers.JSONRenderer",)


def test_database_url_drives_engine(monkeypatch):
    s = reload_settings(
        monkeypatch,
        DJANGO_SECRET_KEY="t",
        DATABASE_URL="sqlite:///:memory:",
    )
    assert s.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"

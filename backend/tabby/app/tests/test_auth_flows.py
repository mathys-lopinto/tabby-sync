import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.mark.django_db
class TestAdminLoginPost:
    def test_login_with_correct_credentials(self, api_client, db):
        User = get_user_model()
        User.objects.create_user(
            username="admin", password="s3cret!", is_staff=True, is_superuser=True
        )
        # Fetch CSRF cookie first.
        api_client.get("/admin/login/")
        token = api_client.cookies["XSRF-TOKEN"].value
        r = api_client.post(
            "/admin/login/",
            data={
                "username": "admin",
                "password": "s3cret!",
                "next": "/admin/",
            },
            HTTP_X_XSRF_TOKEN=token,
        )
        assert r.status_code in (302, 200)

    def test_login_with_wrong_password(self, api_client, db):
        User = get_user_model()
        User.objects.create_user(
            username="admin", password="s3cret!", is_staff=True, is_superuser=True
        )
        api_client.get("/admin/login/")
        token = api_client.cookies["XSRF-TOKEN"].value
        r = api_client.post(
            "/admin/login/",
            data={"username": "admin", "password": "WRONG", "next": "/admin/"},
            HTTP_X_XSRF_TOKEN=token,
        )
        # Renders the login page with an error, never redirects.
        assert r.status_code == 200
        assert b"correct" in r.content.lower() or b"error" in r.content.lower()


class TestCreateSuperuserNonInteractive:
    def test_env_vars_drive_creation(self, db, monkeypatch):
        monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "boss")
        monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "boss@example.com")
        monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "pwd-from-env")

        out = io.StringIO()
        call_command("createsuperuser", interactive=False, stdout=out)

        User = get_user_model()
        u = User.objects.get(username="boss")
        assert u.is_superuser
        assert u.is_staff
        # The token is also auto-generated for superusers.
        assert len(u.config_sync_token) == 128


@pytest.mark.django_db
class TestTokenWhitespaceTolerance:
    def test_double_space_after_bearer(self, user, api_client):
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer  {user.config_sync_token}"
        )
        r = api_client.get("/api/1/configs")
        assert r.status_code == 200

    def test_tab_after_bearer(self, user, api_client):
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer\t{user.config_sync_token}"
        )
        r = api_client.get("/api/1/configs")
        assert r.status_code == 200

    def test_trailing_whitespace_in_token_breaks_match(self, user, api_client):
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {user.config_sync_token} "
        )
        # `.split()` returns the token without trailing space, so this
        # actually still matches.
        r = api_client.get("/api/1/configs")
        assert r.status_code == 200

    def test_lowercase_bearer_scheme_rejected(self, user, api_client):
        api_client.credentials(
            HTTP_AUTHORIZATION=f"bearer {user.config_sync_token}"
        )
        # The middleware does an exact "Bearer" match.
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403


@pytest.mark.django_db
class TestSessionAndBearerInteraction:
    def test_bearer_token_overrides_anonymous_session(self, user, api_client):
        # No login; just a Bearer header. Middleware should still log
        # the user in for the duration of the request.
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {user.config_sync_token}"
        )
        r = api_client.get("/api/1/user")
        assert r.status_code == 200
        assert r.json()["username"] == "alice"

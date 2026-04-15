import io
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from tabby.app.models import hash_token

User = get_user_model()
TOKEN_RE = re.compile(r"[0-9a-f]{128}")


def run(name, *args):
    out, err = io.StringIO(), io.StringIO()
    call_command(name, *args, stdout=out, stderr=err)
    return out.getvalue().strip(), err.getvalue()


def bearer(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
class TestCreateSyncUser:
    def test_creates_user_and_prints_token(self):
        stdout, stderr = run("create_sync_user", "alice")
        assert TOKEN_RE.fullmatch(stdout)
        assert "created sync user 'alice'" in stderr

        user = User.objects.get(username="alice")
        assert user.config_sync_token_hash == hash_token(stdout)
        assert not user.has_usable_password()

    def test_email_optional(self):
        run("create_sync_user", "alice", "--email", "alice@example.com")
        assert User.objects.get(username="alice").email == "alice@example.com"

    def test_duplicate_username_fails(self):
        run("create_sync_user", "alice")
        with pytest.raises(CommandError, match="already exists"):
            run("create_sync_user", "alice")

    def test_printed_token_authenticates_against_api(self):
        token, _ = run("create_sync_user", "alice")

        r = bearer(token).get("/api/1/user")
        assert r.status_code == 200
        assert r.json()["username"] == "alice"

    def test_printed_token_can_create_and_read_configs(self):
        token, _ = run("create_sync_user", "alice")
        client = bearer(token)

        r = client.post(
            "/api/1/configs",
            data={"name": "laptop", "content": '{"x":1}'},
            format="json",
        )
        assert r.status_code == 201

        r = client.get("/api/1/configs")
        assert r.status_code == 200
        assert [c["name"] for c in r.json()] == ["laptop"]

    def test_defensive_error_if_save_skips_token(self, monkeypatch):
        """If someone patches User.save so it doesn't generate a token
        (e.g. by pre-populating the hash), the command must not silently
        hand out an empty token."""

        def broken_save(self, *args, **kwargs):
            self.config_sync_token_hash = "0" * 64
            super(type(self), self).save(*args, **kwargs)

        monkeypatch.setattr(User, "save", broken_save)
        with pytest.raises(CommandError, match="no cleartext token"):
            run("create_sync_user", "alice")


@pytest.mark.django_db
class TestRefreshToken:
    def test_rotates_token(self, user):
        original_hash = user.config_sync_token_hash
        stdout, stderr = run("refresh_token", user.username)

        assert TOKEN_RE.fullmatch(stdout)
        assert f"rotated sync token for {user.username!r}" in stderr

        user.refresh_from_db()
        assert user.config_sync_token_hash != original_hash
        assert user.config_sync_token_hash == hash_token(stdout)

    def test_unknown_username_fails(self, db):
        with pytest.raises(CommandError, match="does not exist"):
            run("refresh_token", "ghost")

    def test_new_token_authenticates_old_one_does_not(self, user):
        old_token = user._just_generated_token

        new_token, _ = run("refresh_token", user.username)

        # Old token is now rejected.
        r = bearer(old_token).get("/api/1/user")
        assert r.status_code == 403

        # New token grants access to the same user.
        r = bearer(new_token).get("/api/1/user")
        assert r.status_code == 200
        assert r.json()["username"] == user.username

    def test_refreshed_token_preserves_user_data(self, user):
        from tabby.app.models import Config

        Config.objects.create(user=user, name="laptop", content='{"x":1}')

        new_token, _ = run("refresh_token", user.username)

        r = bearer(new_token).get("/api/1/configs")
        assert r.status_code == 200
        assert [c["name"] for c in r.json()] == ["laptop"]

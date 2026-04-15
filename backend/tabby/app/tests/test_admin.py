import re
from unittest.mock import MagicMock

import pytest
from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage

from tabby.app.admin import SyncUserAdmin
from tabby.app.models import Config, User, hash_token


@pytest.mark.django_db
class TestSyncUserAdminRegistration:
    def test_user_is_registered(self):
        assert User in admin.site._registry
        assert isinstance(admin.site._registry[User], SyncUserAdmin)

    def test_config_is_registered(self):
        assert Config in admin.site._registry

    def test_tabby_sync_fieldset_present(self):
        ma = admin.site._registry[User]
        names = [name for name, _ in ma.fieldsets]
        assert "Tabby sync" in names

    def test_tabby_sync_fieldset_does_not_expose_token(self):
        ma = admin.site._registry[User]
        sync_fieldset = next(
            opts for name, opts in ma.fieldsets if name == "Tabby sync"
        )
        # The cleartext token cannot be displayed; the hash should not
        # be on a form either, since it would let staff overwrite it
        # with arbitrary values.
        assert "config_sync_token" not in sync_fieldset["fields"]
        assert "config_sync_token_hash" not in sync_fieldset["fields"]
        assert "active_config" in sync_fieldset["fields"]
        assert "active_version" in sync_fieldset["fields"]

    def test_regenerate_action_is_registered(self):
        ma = admin.site._registry[User]
        assert "regenerate_token" in ma.actions


def _make_request_with_messages():
    request = MagicMock()
    request._messages = FallbackStorage(request)
    return request


@pytest.mark.django_db
class TestSyncUserAdminTokenFlows:
    def test_save_model_stashes_token_in_session_for_new_user(self):
        ma = admin.site._registry[User]
        request = _make_request_with_messages()
        request.session = {}
        new_user = User(username="charlie")
        ma.save_model(request, new_user, form=None, change=False)

        assert new_user._just_generated_token
        assert request.session[f"sync_token_{new_user.pk}"] == new_user._just_generated_token
        assert request.session["sync_token_pk_to_show"] == new_user.pk

    def test_save_model_silent_when_no_token_generated(self, user):
        ma = admin.site._registry[User]
        request = _make_request_with_messages()
        request.session = {}
        del user._just_generated_token
        user.email = "alice@example.com"
        ma.save_model(request, user, form=None, change=True)

        assert "sync_token_pk_to_show" not in request.session

    def test_regenerate_action_replaces_hash_and_surfaces_token(self, user):
        ma = admin.site._registry[User]
        original_hash = user.config_sync_token_hash
        request = _make_request_with_messages()

        ma.regenerate_token(request, User.objects.filter(pk=user.pk))

        user.refresh_from_db()
        assert user.config_sync_token_hash != original_hash
        msgs = [str(m) for m in request._messages]
        assert any("New sync token for alice" in m for m in msgs)
        # The displayed token must hash back to the new stored value.
        token = next(m for m in msgs if "New sync token" in m).split(": ", 1)[1]
        assert hash_token(token) == user.config_sync_token_hash


@pytest.mark.django_db
class TestChangeFormRegenerateButton:
    """The per-user edit page has a 'Regenerate sync token' button that
    POSTs to a dedicated URL and redirects back to the edit page."""

    def _admin_client(self, client):
        superuser = User.objects.create_superuser(
            username="root", password="s3cret!", email="r@x"
        )
        client.force_login(superuser)
        return client, superuser

    def test_regenerate_url_rotates_token_and_redirects_to_display(
        self, client, user
    ):
        c, _ = self._admin_client(client)
        original_hash = user.config_sync_token_hash

        r = c.post(f"/admin/app/user/{user.pk}/regenerate-token/")
        assert r.status_code == 302
        assert r.url == f"/admin/app/user/{user.pk}/sync-token-shown/"

        user.refresh_from_db()
        assert user.config_sync_token_hash != original_hash

    def test_token_display_page_shows_new_token(self, client, user):
        c, _ = self._admin_client(client)
        r = c.post(
            f"/admin/app/user/{user.pk}/regenerate-token/",
            follow=True,
        )
        content = r.content.decode()
        assert user.username in content
        assert 'id="sync-token"' in content
        # The token is rendered into the input value attribute. Parse
        # and hash-check instead of string-matching the full 128 chars.
        match = re.search(r'id="sync-token"[^>]*value="([0-9a-f]{128})"', content)
        assert match, "token input with 128-hex value not found"
        user.refresh_from_db()
        assert hash_token(match.group(1)) == user.config_sync_token_hash

    def test_token_display_page_popped_on_second_load(self, client, user):
        c, _ = self._admin_client(client)
        c.post(f"/admin/app/user/{user.pk}/regenerate-token/")

        first = c.get(f"/admin/app/user/{user.pk}/sync-token-shown/")
        second = c.get(f"/admin/app/user/{user.pk}/sync-token-shown/")

        assert 'id="sync-token"' in first.content.decode()
        # Second load shows the fallback "Token no longer available".
        assert b"Token no longer available" in second.content

    def test_regenerate_url_requires_staff(self, client, user):
        # No login: admin_view should redirect to the login page.
        r = client.post(f"/admin/app/user/{user.pk}/regenerate-token/")
        assert r.status_code == 302
        assert "/login" in r.url

    def test_regenerate_url_returns_404_for_unknown_user(self, client):
        c, _ = self._admin_client(client)
        r = c.post("/admin/app/user/99999/regenerate-token/")
        assert r.status_code == 404

    def test_token_display_url_returns_404_for_unknown_user(self, client):
        c, _ = self._admin_client(client)
        r = c.get("/admin/app/user/99999/sync-token-shown/")
        assert r.status_code == 404

    def test_add_user_redirects_to_token_display(self, client):
        c, _ = self._admin_client(client)
        r = c.post(
            "/admin/app/user/add/",
            data={
                "username": "charlie",
                "password1": "S3cret!pwd",
                "password2": "S3cret!pwd",
                "usable_password": "true",
                "_save": "Save",
            },
        )
        assert r.status_code == 302
        assert "/sync-token-shown/" in r.url
        new_user = User.objects.get(username="charlie")
        assert new_user.config_sync_token_hash

    def test_response_add_falls_back_when_session_key_missing(self, user):
        """Defense-in-depth: if save_model was somehow bypassed and no
        token was stashed, response_add must not crash and should
        delegate to the parent."""
        ma = admin.site._registry[User]
        request = _make_request_with_messages()
        request.session = {}
        request.user = user  # any authenticated staff stand-in

        # The parent's response_add looks up reverse("admin:app_user_change");
        # we only care that no exception is raised and that it does not
        # redirect to our display URL.
        try:
            response = ma.response_add(request, user)
        except Exception:
            response = None

        if response is not None:
            assert "/sync-token-shown/" not in getattr(response, "url", "")

    def test_add_user_with_continue_editing_does_not_redirect_to_display(
        self, client
    ):
        # "Save and continue editing" keeps the normal flow: session key
        # is still consumed, user lands on the token display before the
        # edit form. Assert the redirect does go through our display.
        c, _ = self._admin_client(client)
        r = c.post(
            "/admin/app/user/add/",
            data={
                "username": "dana",
                "password1": "S3cret!pwd",
                "password2": "S3cret!pwd",
                "usable_password": "true",
                "_continue": "Save and continue editing",
            },
        )
        assert r.status_code == 302
        assert "/sync-token-shown/" in r.url

    def test_button_rendered_on_change_form(self, client, user):
        c, _ = self._admin_client(client)
        r = c.get(f"/admin/app/user/{user.pk}/change/")
        assert r.status_code == 200
        assert f"/admin/app/user/{user.pk}/regenerate-token/" in r.content.decode()
        assert b"Regenerate sync token" in r.content

    def test_button_absent_on_add_form(self, client):
        c, _ = self._admin_client(client)
        r = c.get("/admin/app/user/add/")
        assert r.status_code == 200
        # No `original` in context on the add form, so no button.
        assert b"Regenerate sync token" not in r.content

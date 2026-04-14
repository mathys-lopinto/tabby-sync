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
    def test_save_model_surfaces_token_for_new_user(self):
        ma = admin.site._registry[User]
        request = _make_request_with_messages()
        new_user = User(username="charlie")
        ma.save_model(request, new_user, form=None, change=False)

        msgs = list(request._messages)
        assert any("Sync token for charlie" in str(m) for m in msgs)
        assert hasattr(new_user, "_just_generated_token")

    def test_save_model_silent_when_no_token_generated(self, user):
        ma = admin.site._registry[User]
        request = _make_request_with_messages()
        # Existing user, just changing email; no new token.
        del user._just_generated_token
        user.email = "alice@example.com"
        ma.save_model(request, user, form=None, change=True)

        msgs = list(request._messages)
        assert all("Sync token" not in str(m) for m in msgs)

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

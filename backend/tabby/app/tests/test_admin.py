import pytest
from django.contrib import admin

from tabby.app.admin import SyncUserAdmin
from tabby.app.models import Config, User


@pytest.mark.django_db
class TestSyncUserAdmin:
    def test_user_is_registered(self):
        assert User in admin.site._registry
        assert isinstance(admin.site._registry[User], SyncUserAdmin)

    def test_config_is_registered(self):
        assert Config in admin.site._registry

    def test_tabby_sync_fieldset_present(self):
        ma = admin.site._registry[User]
        names = [name for name, _ in ma.fieldsets]
        assert "Tabby sync" in names

    def test_tabby_sync_fieldset_contains_token(self):
        ma = admin.site._registry[User]
        sync_fieldset = next(opts for name, opts in ma.fieldsets if name == "Tabby sync")
        assert "config_sync_token" in sync_fieldset["fields"]
        assert "active_config" in sync_fieldset["fields"]
        assert "active_version" in sync_fieldset["fields"]

    def test_token_is_read_only(self):
        ma = admin.site._registry[User]
        assert "config_sync_token" in ma.readonly_fields

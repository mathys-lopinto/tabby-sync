import re
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from tabby.app.models import Config, User, hash_token


@pytest.mark.django_db
class TestUserToken:
    def test_token_is_auto_generated_on_create(self):
        u = User.objects.create(username="alice")
        token = u._just_generated_token
        assert re.fullmatch(r"[0-9a-f]{128}", token)

    def test_hash_is_stored_not_cleartext(self):
        u = User.objects.create(username="alice")
        assert u.config_sync_token_hash == hash_token(u._just_generated_token)
        assert len(u.config_sync_token_hash) == 64

    def test_two_users_get_distinct_tokens(self):
        u1 = User.objects.create(username="alice")
        u2 = User.objects.create(username="bob")
        assert u1._just_generated_token != u2._just_generated_token
        assert u1.config_sync_token_hash != u2.config_sync_token_hash

    def test_hash_preserved_on_subsequent_save(self):
        u = User.objects.create(username="alice")
        original_hash = u.config_sync_token_hash
        u.email = "alice@example.com"
        u.save()
        u.refresh_from_db()
        assert u.config_sync_token_hash == original_hash

    def test_set_new_token_returns_cleartext_and_replaces_hash(self):
        u = User.objects.create(username="alice")
        original_hash = u.config_sync_token_hash
        new_token = u.set_new_token()
        u.save()
        u.refresh_from_db()
        assert re.fullmatch(r"[0-9a-f]{128}", new_token)
        assert u.config_sync_token_hash != original_hash
        assert u.config_sync_token_hash == hash_token(new_token)

    def test_clearing_hash_regenerates_token_on_save(self):
        u = User.objects.create(username="alice")
        u.config_sync_token_hash = ""
        u.save()
        assert re.fullmatch(r"[0-9a-f]{128}", u._just_generated_token)
        assert u.config_sync_token_hash == hash_token(u._just_generated_token)

    def test_username_must_be_unique(self):
        User.objects.create(username="alice")
        with pytest.raises(IntegrityError):
            User.objects.create(username="alice")

    def test_hash_token_is_deterministic(self):
        assert hash_token("abc") == hash_token("abc")
        assert hash_token("abc") != hash_token("abd")
        assert len(hash_token("anything")) == 64


@pytest.mark.django_db
class TestConfig:
    def test_default_name_when_blank(self, user):
        c = Config.objects.create(user=user, name="")
        assert c.name == f"Unnamed config ({date.today()})"

    def test_explicit_name_kept(self, user):
        c = Config.objects.create(user=user, name="my-laptop")
        assert c.name == "my-laptop"

    def test_default_content_is_empty_json_object(self, user):
        c = Config.objects.create(user=user, name="x")
        assert c.content == "{}"

    def test_user_relation(self, user):
        c = Config.objects.create(user=user, name="x")
        assert c in user.configs.all()

    def test_cascade_on_user_delete(self, user):
        Config.objects.create(user=user, name="x")
        Config.objects.create(user=user, name="y")
        user.delete()
        assert Config.objects.count() == 0

    def test_name_max_length_enforced_by_validation(self, user):
        c = Config(user=user, name="a" * 256)
        with pytest.raises(ValidationError):
            c.full_clean()

    def test_unicode_name_preserved(self, user):
        name = "Émilie's 🦊 sync"
        c = Config.objects.create(user=user, name=name)
        c.refresh_from_db()
        assert c.name == name

    def test_large_content(self, user):
        big = "x" * 5_000_000
        c = Config.objects.create(user=user, name="big", content=big)
        c.refresh_from_db()
        assert len(c.content) == 5_000_000

    def test_modified_at_updates_on_save(self, user):
        c = Config.objects.create(user=user, name="x")
        first = c.modified_at
        c.content = '{"changed":true}'
        c.save()
        c.refresh_from_db()
        assert c.modified_at >= first

    def test_str_returns_name(self, user):
        c = Config.objects.create(user=user, name="my-laptop")
        assert str(c) == "my-laptop"

    def test_active_config_set_null_when_target_deleted(self, user):
        c = Config.objects.create(user=user, name="x")
        user.active_config = c
        user.save()
        c.delete()
        user.refresh_from_db()
        assert user.active_config is None

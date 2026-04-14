import pytest


@pytest.mark.django_db
class TestUserEndpoint:
    def test_get_returns_current_user(self, user, authed_client):
        r = authed_client.get("/api/1/user")
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "alice"
        assert body["id"] == user.id

    def test_token_value_never_leaks(self, authed_client):
        r = authed_client.get("/api/1/user")
        body = r.json()
        # The key is kept for backwards compatibility with older Tabby
        # builds that read it, but the value is always null.
        assert body["config_sync_token"] is None
        assert "config_sync_token_hash" not in body

    def test_token_field_is_read_only(self, user, authed_client):
        # Sending a value back must not be persisted anywhere.
        r = authed_client.patch(
            "/api/1/user",
            data={"config_sync_token": "x" * 128},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        # Still hashed, still the original.
        from tabby.app.models import hash_token
        assert user.config_sync_token_hash == hash_token(
            user._just_generated_token
        )

    def test_unauthenticated_is_forbidden(self, api_client):
        r = api_client.get("/api/1/user")
        assert r.status_code == 403

    def test_username_is_read_only(self, user, authed_client):
        r = authed_client.put(
            "/api/1/user",
            data={"username": "renamed", "active_config": None},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.username == "alice"

    def test_active_config_can_be_set_via_put(self, user, config, authed_client):
        r = authed_client.put(
            "/api/1/user",
            data={"active_config": config.id},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.active_config_id == config.id


@pytest.mark.django_db
class TestUserMethodsNotAllowed:
    def test_post_not_allowed(self, authed_client):
        r = authed_client.post("/api/1/user", data={}, format="json")
        assert r.status_code == 405

    def test_delete_not_allowed(self, authed_client):
        r = authed_client.delete("/api/1/user")
        assert r.status_code == 405


@pytest.mark.django_db
class TestScopedActiveConfigDefenseInDepth:
    def test_get_queryset_empty_for_anonymous(self, db):
        from tabby.app.api.user import ScopedActiveConfig

        field = ScopedActiveConfig(allow_null=True, required=False)
        field._context = {}
        assert list(field.get_queryset()) == []


@pytest.mark.django_db
class TestUserPatch:
    def test_patch_partial_update_active_config(self, user, config, authed_client):
        r = authed_client.patch(
            "/api/1/user",
            data={"active_config": config.id},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.active_config_id == config.id

    def test_patch_partial_update_active_version(self, user, authed_client):
        r = authed_client.patch(
            "/api/1/user",
            data={"active_version": "1.0.220"},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.active_version == "1.0.220"


@pytest.mark.django_db
class TestUserCrossUserSafety:
    def test_cannot_assign_other_users_config_as_active(
        self, user, other_user, authed_client
    ):
        from tabby.app.models import Config

        their = Config.objects.create(user=other_user, name="theirs")
        r = authed_client.patch(
            "/api/1/user",
            data={"active_config": their.id},
            format="json",
        )
        assert r.status_code == 400
        assert "active_config" in r.json()
        user.refresh_from_db()
        assert user.active_config_id is None


@pytest.mark.django_db
class TestUserActiveConfigEdgeCases:
    def test_setting_nonexistent_active_config(self, user, authed_client):
        r = authed_client.patch(
            "/api/1/user",
            data={"active_config": 99999999},
            format="json",
        )
        assert r.status_code == 400
        user.refresh_from_db()
        assert user.active_config_id is None

    def test_clearing_active_config(self, user, config, authed_client):
        user.active_config = config
        user.save()
        r = authed_client.patch(
            "/api/1/user",
            data={"active_config": None},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.active_config_id is None

    def test_active_config_nulls_when_target_deleted(
        self, user, config, authed_client
    ):
        user.active_config = config
        user.save()
        config.delete()
        r = authed_client.get("/api/1/user")
        assert r.status_code == 200
        assert r.json()["active_config"] is None

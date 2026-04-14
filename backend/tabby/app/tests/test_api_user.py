import pytest


@pytest.mark.django_db
class TestUserEndpoint:
    def test_get_returns_current_user(self, user, authed_client):
        r = authed_client.get("/api/1/user")
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "alice"
        assert body["id"] == user.id
        assert body["config_sync_token"] == user.config_sync_token

    def test_unauthenticated_is_forbidden(self, api_client):
        r = api_client.get("/api/1/user")
        assert r.status_code == 403

    def test_username_is_read_only(self, user, authed_client):
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "username": "renamed",
                "config_sync_token": user.config_sync_token,
                "active_config": None,
            },
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.username == "alice"

    def test_active_config_can_be_set(self, user, config, authed_client):
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "config_sync_token": user.config_sync_token,
                "active_config": config.id,
            },
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

    def test_patch_not_allowed(self, authed_client):
        r = authed_client.patch("/api/1/user", data={}, format="json")
        assert r.status_code == 405


@pytest.mark.django_db
class TestUserCrossUserSafety:
    def test_assigning_other_users_active_config_is_currently_accepted(
        self, user, other_user, authed_client
    ):
        # Documents current behavior: the serializer does not scope
        # active_config to the requesting user. If this becomes a
        # security concern, scope the queryset on the field.
        from tabby.app.models import Config

        their = Config.objects.create(user=other_user, name="theirs")
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "config_sync_token": user.config_sync_token,
                "active_config": their.id,
            },
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.active_config_id == their.id


@pytest.mark.django_db
class TestUserSyncTokenField:
    """The token is the auth credential. The endpoint exposes it as
    writable, so the client can rotate it through PUT."""

    def test_token_shown_in_response(self, user, authed_client):
        r = authed_client.get("/api/1/user")
        assert r.json()["config_sync_token"] == user.config_sync_token

    def test_token_can_be_rotated_through_put(self, user, authed_client):
        new_token = "z" * 128
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "config_sync_token": new_token,
                "active_config": None,
            },
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.config_sync_token == new_token

    def test_user_cannot_set_other_users_token(
        self, user, other_user, authed_client
    ):
        # Even if the client tries the other user's token, the endpoint
        # only mutates the requesting user.
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "config_sync_token": other_user.config_sync_token,
                "active_config": None,
            },
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        other_user.refresh_from_db()
        # The requesting user's own token was overwritten with the
        # supplied value, but the other user is untouched.
        assert user.config_sync_token == other_user.config_sync_token


@pytest.mark.django_db
class TestUserActiveConfigEdgeCases:
    def test_setting_nonexistent_active_config(self, user, authed_client):
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "config_sync_token": user.config_sync_token,
                "active_config": 99999999,
            },
            format="json",
        )
        assert r.status_code == 400
        user.refresh_from_db()
        assert user.active_config_id is None

    def test_clearing_active_config(self, user, config, authed_client):
        user.active_config = config
        user.save()
        r = authed_client.put(
            "/api/1/user",
            data={
                "id": user.id,
                "config_sync_token": user.config_sync_token,
                "active_config": None,
            },
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

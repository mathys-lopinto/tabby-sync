import pytest

from tabby.app.models import Config, User


@pytest.mark.django_db
class TestTabbyDesktopFlow:
    """Walk through the API the way a Tabby desktop client would."""

    def test_full_sync_flow(self, authed_client, user):
        # 1. The client introduces itself.
        r = authed_client.get("/api/1/user")
        assert r.status_code == 200
        me = r.json()
        assert me["username"] == "alice"
        assert me["active_config"] is None

        # 2. The client lists existing configs (none yet).
        r = authed_client.get("/api/1/configs")
        assert r.status_code == 200
        assert r.json() == []

        # 3. The client uploads its first config.
        r = authed_client.post(
            "/api/1/configs",
            data={"name": "laptop", "content": '{"theme":"dark"}'},
            format="json",
        )
        assert r.status_code == 201
        first = r.json()
        assert first["user"] == user.id

        # 4. The client marks it as the active one (PATCH for partial update).
        r = authed_client.patch(
            "/api/1/user",
            data={"active_config": first["id"]},
            format="json",
        )
        assert r.status_code == 200

        # 5. Later, the client changes the config (new theme).
        r = authed_client.patch(
            f"/api/1/configs/{first['id']}",
            data={"content": '{"theme":"light"}'},
            format="json",
        )
        assert r.status_code == 200

        # 6. The client uploads a second config from another machine.
        r = authed_client.post(
            "/api/1/configs",
            data={"name": "desktop", "content": "{}"},
            format="json",
        )
        assert r.status_code == 201

        # 7. Final state from the client's perspective.
        r = authed_client.get("/api/1/configs")
        assert {c["name"] for c in r.json()} == {"laptop", "desktop"}

        r = authed_client.get(f"/api/1/configs/{first['id']}")
        assert r.json()["content"] == '{"theme":"light"}'

        r = authed_client.get("/api/1/user")
        assert r.json()["active_config"] == first["id"]

        # 8. Database state matches.
        assert Config.objects.filter(user=user).count() == 2
        user.refresh_from_db()
        assert user.active_config_id == first["id"]

    def test_two_users_are_isolated(self, authed_client, other_authed_client, user, other_user):
        authed_client.post(
            "/api/1/configs",
            data={"name": "alice-only", "content": "{}"},
            format="json",
        )
        other_authed_client.post(
            "/api/1/configs",
            data={"name": "bob-only", "content": "{}"},
            format="json",
        )

        a = authed_client.get("/api/1/configs").json()
        b = other_authed_client.get("/api/1/configs").json()

        assert {c["name"] for c in a} == {"alice-only"}
        assert {c["name"] for c in b} == {"bob-only"}
        assert User.objects.count() == 2
        assert Config.objects.count() == 2

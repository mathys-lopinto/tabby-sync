import pytest


@pytest.mark.django_db
class TestTokenMiddleware:
    def test_no_token_no_auth(self, api_client):
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403

    def test_invalid_bearer_token(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403

    def test_valid_bearer_token(self, user, api_client):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {user.config_sync_token}")
        r = api_client.get("/api/1/configs")
        assert r.status_code == 200

    def test_query_param_token(self, user, api_client):
        r = api_client.get(f"/api/1/configs?auth_token={user.config_sync_token}")
        assert r.status_code == 200

    def test_malformed_authorization_header(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Malformed")
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403

    def test_non_bearer_scheme_ignored(self, user, api_client):
        api_client.credentials(HTTP_AUTHORIZATION=f"Basic {user.config_sync_token}")
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403

    def test_empty_bearer_value(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer ")
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403

    def test_empty_query_param(self, api_client):
        r = api_client.get("/api/1/configs?auth_token=")
        assert r.status_code == 403

    def test_inactive_user_is_rejected(self, user, api_client):
        # Django's ModelBackend.user_can_authenticate returns False when
        # is_active is False, so login() refuses to set the session.
        user.is_active = False
        user.save()
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {user.config_sync_token}")
        r = api_client.get("/api/1/configs")
        assert r.status_code == 403

    def test_query_param_overridden_by_header(self, user, other_user, api_client):
        # Header is read after the query param, so it wins.
        api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {other_user.config_sync_token}"
        )
        r = api_client.get(f"/api/1/configs?auth_token={user.config_sync_token}")
        assert r.status_code == 200
        # The response should reflect other_user, not user.
        assert r.json() == []

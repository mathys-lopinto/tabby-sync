import pytest


@pytest.mark.django_db
class TestOptions:
    def test_options_collection(self, authed_client):
        r = authed_client.options("/api/1/configs")
        assert r.status_code == 200
        # DRF returns endpoint metadata as JSON.
        assert "name" in r.json()

    def test_options_detail(self, authed_client, config):
        r = authed_client.options(f"/api/1/configs/{config.id}")
        assert r.status_code == 200

    def test_options_user(self, authed_client):
        r = authed_client.options("/api/1/user")
        assert r.status_code == 200

    def test_options_includes_allow_header(self, authed_client):
        r = authed_client.options("/api/1/user")
        assert "Allow" in r.headers
        allow = r["Allow"].upper()
        assert "GET" in allow
        assert "PUT" in allow
        assert "PATCH" in allow
        assert "DELETE" not in allow
        assert "POST" not in allow


@pytest.mark.django_db
class TestAcceptHeader:
    def test_accept_html_returns_json_anyway(self, authed_client):
        # Only JSONRenderer is configured, so DRF falls back to it
        # regardless of what the client asks for.
        r = authed_client.get("/api/1/configs", HTTP_ACCEPT="text/html")
        # 200 with JSON body, or 406 Not Acceptable depending on DRF.
        assert r.status_code in (200, 406)
        if r.status_code == 200:
            assert r["Content-Type"].startswith("application/json")

    def test_accept_xml_returns_406_or_json(self, authed_client):
        r = authed_client.get("/api/1/configs", HTTP_ACCEPT="application/xml")
        assert r.status_code in (200, 406)

    def test_accept_json_is_honored(self, authed_client):
        r = authed_client.get("/api/1/configs", HTTP_ACCEPT="application/json")
        assert r.status_code == 200
        assert r["Content-Type"].startswith("application/json")


@pytest.mark.django_db
class TestContentTypeOnPost:
    def test_post_with_text_plain_is_rejected(self, authed_client):
        r = authed_client.post(
            "/api/1/configs",
            data='{"name":"x","content":"{}"}',
            content_type="text/plain",
        )
        # DRF only has the JSON parser registered, so a non-JSON
        # content-type triggers Unsupported Media Type.
        assert r.status_code == 415

    def test_post_with_no_body_and_json_type(self, authed_client):
        r = authed_client.post(
            "/api/1/configs",
            data="",
            content_type="application/json",
        )
        # Empty body, JSON parser: could be 400 (parse error) or 201
        # (everything optional). Both are acceptable; never 5xx.
        assert r.status_code < 500

    def test_post_with_invalid_json(self, authed_client):
        r = authed_client.post(
            "/api/1/configs",
            data="{not-json",
            content_type="application/json",
        )
        assert r.status_code == 400


@pytest.mark.django_db
class TestFieldsRarelyExercised:
    def test_last_used_with_version_round_trip(self, authed_client):
        r = authed_client.post(
            "/api/1/configs",
            data={
                "name": "x",
                "content": "{}",
                "last_used_with_version": "1.0.220",
            },
            format="json",
        )
        assert r.status_code == 201
        cid = r.json()["id"]

        r = authed_client.get(f"/api/1/configs/{cid}")
        assert r.json()["last_used_with_version"] == "1.0.220"

    def test_active_version_round_trip(self, user, authed_client):
        r = authed_client.patch(
            "/api/1/user",
            data={"active_version": "1.0.220"},
            format="json",
        )
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.active_version == "1.0.220"

    def test_user_serializer_exposes_expected_fields(self, user, authed_client):
        r = authed_client.get("/api/1/user")
        assert set(r.json().keys()) == {
            "id",
            "username",
            "active_config",
            "active_version",
            "config_sync_token",
        }
        # The placeholder must always be null.
        assert r.json()["config_sync_token"] is None

    def test_config_serializer_fields(self, config, authed_client):
        r = authed_client.get(f"/api/1/configs/{config.id}")
        body = r.json()
        # `fields = "__all__"` exposes everything on the model.
        assert {
            "id",
            "user",
            "name",
            "content",
            "last_used_with_version",
            "created_at",
            "modified_at",
        } <= set(body.keys())

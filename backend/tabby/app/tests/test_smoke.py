import io

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestAdminSmoke:
    def test_admin_redirects_to_login(self, api_client):
        r = api_client.get("/admin/")
        assert r.status_code in (301, 302)
        assert "/login" in r.url

    def test_admin_login_page_renders(self, api_client):
        r = api_client.get("/admin/login/")
        assert r.status_code == 200
        assert b"username" in r.content.lower()


class TestManagementCommands:
    def test_check_passes(self):
        out = io.StringIO()
        call_command("check", stdout=out)
        assert "no issues" in out.getvalue().lower()

    def test_migrate_is_idempotent(self, db):
        out = io.StringIO()
        call_command("migrate", stdout=out, verbosity=0)
        call_command("migrate", stdout=out, verbosity=0)


@pytest.mark.django_db
class TestUrls:
    def test_root_returns_404(self, authed_client):
        # SimpleRouter (vs DefaultRouter) does not expose a discovery
        # index, so / is unmatched.
        r = authed_client.get("/")
        assert r.status_code == 404

    def test_unknown_path_returns_404(self, api_client):
        r = api_client.get("/this/does/not/exist")
        assert r.status_code == 404

    def test_unknown_api_version_returns_404(self, authed_client):
        r = authed_client.get("/api/2/configs")
        assert r.status_code == 404


@pytest.mark.django_db
class TestHealth:
    def test_health_is_200_plain(self, api_client):
        r = api_client.get("/api/health")
        assert r.status_code == 200
        assert r["Content-Type"].startswith("text/plain")
        assert r.content.strip() == b"ok"

    def test_health_requires_no_auth(self, api_client):
        # Explicitly no Bearer header: the endpoint must still answer
        # so uptime checks can reach it without provisioning a user.
        r = api_client.get("/api/health")
        assert r.status_code == 200

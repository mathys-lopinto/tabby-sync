import os

os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-not-secret")

import pytest
from rest_framework.test import APIClient

from tabby.app.models import Config, User


@pytest.fixture
def user(db):
    return User.objects.create(username="alice")


@pytest.fixture
def other_user(db):
    return User.objects.create(username="bob")


@pytest.fixture
def config(db, user):
    return Config.objects.create(user=user, name="laptop", content='{"x":1}')


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {user.config_sync_token}")
    return client


@pytest.fixture
def other_authed_client(other_user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {other_user.config_sync_token}")
    return client

import hashlib
import secrets
from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class Config(models.Model):
    user = models.ForeignKey(
        "app.User", related_name="configs", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    content = models.TextField(default="{}")
    last_used_with_version = models.CharField(max_length=32, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"Unnamed config ({date.today()})"
        super().save(*args, **kwargs)


class User(AbstractUser):
    active_config = models.ForeignKey(
        Config,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    active_version = models.CharField(max_length=32, null=True, blank=True)
    config_sync_token_hash = models.CharField(max_length=64, db_index=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def set_new_token(self) -> str:
        token = secrets.token_hex(64)
        self.config_sync_token_hash = hash_token(token)
        # Stash on the instance so callers (admin, tests) can read it
        # exactly once. Never persisted.
        self._just_generated_token = token
        return token

    def save(self, *args, **kwargs):
        if not self.config_sync_token_hash:
            self.set_new_token()
        super().save(*args, **kwargs)

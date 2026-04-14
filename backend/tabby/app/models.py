import secrets
from datetime import date
from django.db import models
from django.contrib.auth.models import AbstractUser


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
        Config, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    active_version = models.CharField(max_length=32, null=True)
    config_sync_token = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.config_sync_token:
            self.config_sync_token = secrets.token_hex(64)
        super().save(*args, **kwargs)

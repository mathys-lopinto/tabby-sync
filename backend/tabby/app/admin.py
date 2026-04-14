from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Config, User


class SyncUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Tabby sync", {"fields": ("config_sync_token", "active_config", "active_version")}),
    )
    readonly_fields = ("config_sync_token",)


admin.site.register(User, SyncUserAdmin)
admin.site.register(Config)

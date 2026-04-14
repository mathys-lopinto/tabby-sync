from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from .models import Config, User


class SyncUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Tabby sync", {"fields": ("active_config", "active_version")}),
    )

    actions = ["regenerate_token"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        token = getattr(obj, "_just_generated_token", None)
        if token:
            messages.warning(
                request,
                f"Sync token for {obj.username} (copy now, it will not be shown again): {token}",
            )

    @admin.action(description="Regenerate sync token (shown once)")
    def regenerate_token(self, request, queryset):
        for user in queryset:
            token = user.set_new_token()
            user.save()
            messages.warning(
                request,
                f"New sync token for {user.username} (copy now, it will not be shown again): {token}",
            )


admin.site.register(User, SyncUserAdmin)
admin.site.register(Config)

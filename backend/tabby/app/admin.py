from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from .models import Config, User


class SyncUserAdmin(UserAdmin):
    change_form_template = "admin/app/user/change_form.html"

    fieldsets = UserAdmin.fieldsets + (
        ("Tabby sync", {"fields": ("active_config", "active_version")}),
    )

    actions = ["regenerate_token"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        token = getattr(obj, "_just_generated_token", None)
        if token:
            request.session[f"sync_token_{obj.pk}"] = token
            # Picked up by the redirect that UserAdmin emits after
            # a successful add/change, so the staff lands on the
            # token display page.
            request.session["sync_token_pk_to_show"] = obj.pk

    def response_add(self, request, obj, post_url_continue=None):
        pk = request.session.pop("sync_token_pk_to_show", None)
        if pk is not None:
            return HttpResponseRedirect(reverse("admin:app_user_sync_token_shown", args=[pk]))
        return super().response_add(request, obj, post_url_continue)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/regenerate-token/",
                self.admin_site.admin_view(self.regenerate_token_view),
                name="app_user_regenerate_token",
            ),
            path(
                "<path:object_id>/sync-token-shown/",
                self.admin_site.admin_view(self.sync_token_shown_view),
                name="app_user_sync_token_shown",
            ),
        ]
        return custom + urls

    def regenerate_token_view(self, request, object_id):
        user = self.get_object(request, object_id)
        if user is None:
            raise Http404
        token = user.set_new_token()
        user.save()
        request.session[f"sync_token_{user.pk}"] = token
        return HttpResponseRedirect(reverse("admin:app_user_sync_token_shown", args=[user.pk]))

    def sync_token_shown_view(self, request, object_id):
        user = self.get_object(request, object_id)
        if user is None:
            raise Http404
        token = request.session.pop(f"sync_token_{user.pk}", None)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "user_obj": user,
            "token": token,
        }
        return render(request, "admin/app/user/sync_token_shown.html", context)

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

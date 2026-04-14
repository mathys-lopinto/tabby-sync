from django.contrib import admin
from django.urls import include, path

from .app.urls import urlpatterns as app_urlpatterns

urlpatterns = [
    path("", include(app_urlpatterns)),
    path("admin/", admin.site.urls),
]

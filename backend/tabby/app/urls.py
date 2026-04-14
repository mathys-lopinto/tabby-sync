from django.urls import path, include

from . import api


urlpatterns = [
    path("", include(api.urlpatterns)),
]

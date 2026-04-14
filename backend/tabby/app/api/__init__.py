from django.urls import include, path
from rest_framework import routers

from . import config, user

router = routers.SimpleRouter(trailing_slash=False)
router.register("api/1/configs", config.ConfigViewSet)

urlpatterns = [
    path(
        "api/1/user",
        user.UserViewSet.as_view(
            {"get": "retrieve", "put": "update", "patch": "partial_update"}
        ),
    ),
    path("", include(router.urls)),
]

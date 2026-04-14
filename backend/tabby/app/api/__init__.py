from django.urls import path, include
from rest_framework import routers
from . import config, user


router = routers.DefaultRouter(trailing_slash=False)
router.register("api/1/configs", config.ConfigViewSet)

urlpatterns = [
    path("api/1/user", user.UserViewSet.as_view({"get": "retrieve", "put": "update"})),
    path("", include(router.urls)),
]

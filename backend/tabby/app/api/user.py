from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin
from rest_framework.viewsets import GenericViewSet

from ..models import Config, User


class ScopedActiveConfig(serializers.PrimaryKeyRelatedField):
    """Restrict assignable configs to the requesting user's own."""

    def get_queryset(self):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return Config.objects.none()
        return Config.objects.filter(user=request.user)


class UserSerializer(serializers.ModelSerializer):
    active_config = ScopedActiveConfig(allow_null=True, required=False)
    # Backwards-compat placeholder. The real token is hashed at rest and
    # never sent to the client. Older Tabby desktop builds may still read
    # this field; returning null avoids a KeyError on their side without
    # leaking anything.
    config_sync_token = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "active_config",
            "active_version",
            "config_sync_token",
        )
        read_only_fields = ("id", "username", "config_sync_token")

    def get_config_sync_token(self, obj):
        return None


class UserViewSet(RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        raise PermissionDenied()

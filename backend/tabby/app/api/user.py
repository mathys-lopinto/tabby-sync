from rest_framework import fields
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin
from rest_framework.viewsets import GenericViewSet
from rest_framework.serializers import ModelSerializer

from ..models import User


class UserSerializer(ModelSerializer):
    id = fields.IntegerField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "active_config",
            "config_sync_token",
        )
        read_only_fields = ("id", "username")


class UserViewSet(RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_object(self):
        if self.request.user.is_authenticated:
            return self.request.user
        raise PermissionDenied()

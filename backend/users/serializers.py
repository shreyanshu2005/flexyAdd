from __future__ import annotations

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.constants import ROLE_CHOICES
from users.models import User
from users.services import UserService


class UserSerializer(serializers.ModelSerializer):
    workspace = serializers.CharField(source="workspace.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "email", "role", "workspace", "is_active", "created_at"]
        read_only_fields = fields


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, default="VIEWER")

    def create(self, validated_data):
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            validated_data["workspace"] = request.user.workspace  # new users join the creator's workspace
        return UserService.create_user(validated_data)


class RegisterSerializer(serializers.Serializer):
    workspace_name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)


class UserRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ROLE_CHOICES)

    def update(self, instance, validated_data):
        return UserService.assign_role(instance, validated_data["role"])


class UserStatusUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()

    def update(self, instance, validated_data):
        return UserService.set_status(instance, validated_data["is_active"])


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data

from .models import User
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .permissions import IsSuperAdmin


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone_number", "role", "is_active")


class RegisterSerializer(serializers.ModelSerializer):
    password_1 = serializers.CharField(
        write_only=True,
        min_length=8,
    )
    password_2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("phone_number", "password_1", "password_2", "role")

    def validate(self, attrs):
        if attrs["password_1"] != attrs["password_2"]:
            raise serializers.ValidationError({"password_2": "Passwords do not match."})

        role = attrs.get("role", User.Role.MEMBER)
        request = self.context.get("request")
        if role != User.Role.MEMBER:
            request = self.context.get("request")
            if not request or not IsSuperAdmin().has_permission(request, None):
                raise serializers.ValidationError(
                    {
                        "role": (
                            "Only an authenticated admin can create "
                            "staff or admin users."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password_1")
        role = validated_data.pop("role", User.Role.MEMBER)
        validated_data.pop("password_2")
        return User.objects.create_user(
            phone_number=validated_data["phone_number"],
            password=password,
            role=role,
        )


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user = User.objects.get(phone_number=attrs["phone_number"])
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"detail": "Invalid phone number or password."}
            )
        if not user.check_password(attrs["password"]):
            raise serializers.ValidationError(
                {"detail": "Invalid phone number or password."}
            )

        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is inactive."})
        attrs["user"] = user
        return attrs


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class TokenRefreshInputSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            refresh_token = RefreshToken(value)
            return str(refresh_token.access_token)
        except TokenError:
            raise NotAuthenticated("Invalid or expired refresh token.")

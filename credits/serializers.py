from django.utils import timezone
from rest_framework import serializers

from accounts.models import User

from .models import CreditPack, Transaction


class CreditPackSerializer(serializers.ModelSerializer):
    granted_at = serializers.DateTimeField(required=False, default=timezone.now)

    class Meta:
        model = CreditPack
        fields = [
            "id",
            "member",
            "granted_credits",
            "remaining_credits",
            "granted_at",
            "expires_at",
        ]
        read_only_fields = [
            "id",
            "remaining_credits",
        ]

    def validate_member(self, member):
        if member.role != User.Role.MEMBER:
            raise serializers.ValidationError(
                "Credit packs can only be granted to members."
            )
        return member

    def validate(self, attrs):
        granted_at = attrs.get("granted_at") or timezone.now()
        expires_at = attrs.get("expires_at")
        if expires_at and expires_at <= granted_at:
            raise serializers.ValidationError(
                {"expires_at": "Expiry date must be after grant date."}
            )
        return attrs


class CreditPackBalanceItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    granted_credits = serializers.IntegerField()
    remaining_credits = serializers.IntegerField()
    expires_at = serializers.DateTimeField()
    granted_at = serializers.DateTimeField()


class CreditBalanceSerializer(serializers.Serializer):
    as_of = serializers.DateTimeField()
    total_credits = serializers.IntegerField()
    packs = CreditPackBalanceItemSerializer(many=True)


class TransactionSerializer(serializers.ModelSerializer):
    member = serializers.IntegerField(source="pack.member_id", read_only=True)
    cause = serializers.CharField(source="get_description_display", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "member",
            "pack",
            "booking",
            "type",
            "description",
            "cause",
            "amount",
            "created_at",
        ]
        read_only_fields = fields

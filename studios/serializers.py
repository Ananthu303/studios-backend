from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers

from .models import FitnessClass, Studio


class StudioSerializer(serializers.ModelSerializer):
    timezone = serializers.CharField(required=False)

    class Meta:
        model = Studio
        fields = [
            "id",
            "name",
            "timezone",
            "cancellation_cutoff_hours",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_timezone(self, value):
        try:
            ZoneInfo(str(value))
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Invalid IANA timezone.")  # noqa: B904
        return value


class FitnessClassSerializer(serializers.ModelSerializer):
    spots_available = serializers.IntegerField(read_only=True)
    end_time = serializers.DateTimeField(read_only=True)
    confirmed_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = FitnessClass
        fields = [
            "id",
            "studio",
            "name",
            "start_time",
            "end_time",
            "duration_minutes",
            "spots",
            "confirmed_count",
            "spots_available",
            "credit_cost",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "end_time",
            "confirmed_count",
            "spots_available",
            "created_at",
            "updated_at",
        ]

    def validate_start_time(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Class start time must be in the future.")
        return value

    def validate(self, attrs):
        spots = attrs.get("spots")
        if self.instance is not None and spots is not None:
            if spots < self.instance.confirmed_count:
                raise serializers.ValidationError(
                    {
                        "spots": (
                            "Cannot reduce spots below the number of "
                            "confirmed bookings."
                        )
                    }
                )
        return attrs

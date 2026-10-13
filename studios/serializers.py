from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework import serializers
from .models import FitnessClass, Studio


class StudioSerializer(serializers.ModelSerializer):
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
            raise serializers.ValidationError("Invalid IANA timezone.")
        return value


class FitnessClassSerializer(serializers.ModelSerializer):
    spots_available = serializers.SerializerMethodField()
    end_time = serializers.DateTimeField(read_only=True)

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
            "spots_available",
            "credit_cost",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "end_time",
            "spots_available",
            "created_at",
            "updated_at",
        ]

    def get_spots_available(self, obj):
        return obj.spots

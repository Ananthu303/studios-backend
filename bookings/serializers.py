from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    slot_number = serializers.IntegerField(
        source="slot.slot_number",
        read_only=True,
        default=None,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "member",
            "fitness_class",
            "status",
            "slot_number",
            "idempotency_key",
            "booked_at",
            "confirmed_at",
            "cancelled_at",
        ]
        read_only_fields = [
            "id",
            "member",
            "status",
            "slot_number",
            "idempotency_key",
            "booked_at",
            "confirmed_at",
            "cancelled_at",
        ]

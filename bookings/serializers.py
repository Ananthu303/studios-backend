from rest_framework import serializers

from .models import Booking
from .services import cancel_booking


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
            "slot_number",
            "idempotency_key",
            "booked_at",
            "confirmed_at",
            "cancelled_at",
        ]


    def validate_status(self, value):
        if self.instance is not None and value != Booking.Status.CANCELLED:
            raise serializers.ValidationError("Only updating status to CANCELLED is allowed.")
        return value

    def update(self, instance, validated_data):
        new_status = validated_data.get("status", Booking.Status.CANCELLED)
        if new_status == Booking.Status.CANCELLED:
            instance.status = Booking.Status.CANCELLED
            request = self.context.get("request")
            member = (
                request.user
                if (request and hasattr(request, "user") and request.user.is_authenticated)
                else instance.member
            )
            cancelled_booking = cancel_booking(member=member, booking_id=instance.pk)
            return cancelled_booking
        raise serializers.ValidationError({"status": "Only status CANCELLED is allowed."})



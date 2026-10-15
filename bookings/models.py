from django.db import models
from django.db.models import Q

from accounts.models import User
from studios.models import FitnessClass


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        WAITING_LIST = "WAITING_LIST", "Waiting List"
        CANCELLED = "CANCELLED", "Cancelled"

    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    fitness_class = models.ForeignKey(
        FitnessClass,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    idempotency_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    booked_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-booked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="unique_member_booking_idempotency_key",
            ),
            models.UniqueConstraint(
                fields=["member", "fitness_class"],
                condition=Q(
                    status__in=["CONFIRMED", "WAITING_LIST"],
                ),
                name="unique_active_booking_per_member_class",
            ),
        ]
        indexes = [
            models.Index(
                fields=["fitness_class", "status", "booked_at"],
                name="booking_class_status_idx",
            ),
        ]

    @property
    def is_within_cancellation_cutoff(self):
        return self.fitness_class.is_within_cancellation_cutoff

    @property
    def has_started(self):
        return self.fitness_class.has_started


    def __str__(self):
        return f"{self.member} - {self.fitness_class} ({self.status})"


class Slot(models.Model):
    fitness_class = models.ForeignKey(
        FitnessClass,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="slot",
    )
    slot_number = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slot_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["fitness_class", "slot_number"],
                name="unique_slot_per_class",
            ),
        ]

    def __str__(self):
        return f"{self.fitness_class.name} - Slot {self.slot_number}"

from django.db import models
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking


class CreditPack(models.Model):
    member = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="credit_packs",
    )
    granted_credits = models.PositiveIntegerField()
    remaining_credits = models.PositiveIntegerField()
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["expires_at", "granted_at"]

    def __str__(self):
        return f"{self.member} - {self.remaining_credits}/{self.granted_credits}"

    def add_transaction(self, type, description, amount, booking=None, created_at=None):
        return Transaction.objects.create(
            pack=self,
            type=type,
            description=description,
            amount=amount,
            booking=booking,
            **({"created_at": created_at} if created_at else {}),
        )


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        CREDIT = "C", "Credit"
        DEBIT = "D", "Debit"

    class TransactionDescription(models.TextChoices):
        PACK_GRANT = "PG", "Credit Pack Grant"
        BOOKING_CHARGE = "BC", "Booking Charge"
        CANCELLATION_REFUND = "CR", "Cancellation Refund"

    pack = models.ForeignKey(
        CreditPack,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    type = models.CharField(
        max_length=1,
        choices=TransactionType.choices,
    )
    description = models.CharField(
        max_length=2,
        choices=TransactionDescription.choices,
    )
    amount = models.PositiveIntegerField()
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_transactions",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["pack", "created_at", "id"],
                name="credit_tx_pack_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.pack.member} "
            f"{self.get_type_display()} "
            f"{self.amount} "
            f"({self.get_description_display()})"
        )

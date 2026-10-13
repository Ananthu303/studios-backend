from accounts.models import User
from django.db import models
from django.db.models import F, Q


class CreditPack(models.Model):
    member = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="credit_packs",
    )
    granted_credits = models.PositiveIntegerField()
    remaining_credits = models.PositiveIntegerField()
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["expires_at", "granted_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(granted_credits__gt=0),
                name="credit_pack_granted_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    remaining_credits__lte=F("granted_credits"),
                ),
                name="credit_pack_remaining_lte_granted",
            ),
        ]

    def __str__(self):
        return f"{self.member} - " f"{self.remaining_credits}/{self.granted_credits}"


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
    reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="credit_transaction_amount_positive",
            ),
        ]
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

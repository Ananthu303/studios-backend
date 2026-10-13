from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CreditPack, Transaction
from django.db.models import Sum, F


@transaction.atomic
def grant_credit_pack(*, member, credits, expires_at, reference=""):
    if credits <= 0:
        raise ValidationError("Credits must be greater than zero.")
    if expires_at <= timezone.now():
        raise ValidationError("Expiry date must be in the future.")
    pack = CreditPack.objects.create(
        member=member,
        granted_credits=credits,
        remaining_credits=credits,
        expires_at=expires_at,
    )
    Transaction.objects.create(
        pack=pack,
        type=Transaction.TransactionType.CREDIT,
        description=Transaction.TransactionDescription.PACK_GRANT,
        amount=credits,
        reference=reference,
    )
    return pack


def get_credit_balance(*, member):
    now = timezone.now()
    packs = CreditPack.objects.filter(
        member=member,
        expires_at__gt=now,
        remaining_credits__gt=0,
    ).order_by("expires_at", "granted_at")
    total_credits = (
        packs.aggregate(
            total=Sum("remaining_credits"),
        )["total"]
        or 0
    )
    pack_details = [
        {
            "id": pack.id,
            "granted_credits": pack.granted_credits,
            "remaining_credits": pack.remaining_credits,
            "expires_at": pack.expires_at,
        }
        for pack in packs
    ]

    return {
        "total_credits": total_credits,
        "packs": pack_details,
    }


@transaction.atomic
def deduct_credits(*, member, credits, reference=""):
    if credits <= 0:
        raise ValidationError("Credits must be greater than zero.")
    remaining_to_deduct = credits
    now = timezone.now()
    packs = (
        CreditPack.objects.filter(
            member=member,
            expires_at__gt=now,
            remaining_credits__gt=0,
        )
        .order_by("expires_at", "granted_at", "id")
        .select_for_update()
    )

    for pack in packs:
        amount = min(pack.remaining_credits, remaining_to_deduct)
        if amount == 0:
            continue
        updated = CreditPack.objects.filter(
            pk=pack.pk,
            remaining_credits__gte=amount,
        ).update(
            remaining_credits=F("remaining_credits") - amount,
        )
        if not updated:
            raise ValidationError("Credit balance changed. Please try again.")
        Transaction.objects.create(
            pack=pack,
            type=Transaction.TransactionType.DEBIT,
            description=(Transaction.TransactionDescription.BOOKING_CHARGE),
            amount=amount,
            reference=reference,
        )
        remaining_to_deduct -= amount
        if remaining_to_deduct == 0:
            break

    if remaining_to_deduct > 0:
        raise ValidationError("Insufficient credits.")

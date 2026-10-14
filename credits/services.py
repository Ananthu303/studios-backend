from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking

from .models import CreditPack, Transaction


def _aware(moment):
    if moment is None:
        return timezone.now()
    if timezone.is_naive(moment):
        return timezone.make_aware(moment, timezone.get_current_timezone())
    return moment


@transaction.atomic
def grant_credit_pack(member, credits, expires_at, granted_at=None):
    if member.role != User.Role.MEMBER:
        raise ValidationError("Credit packs can only be granted to members.")

    if credits <= 0:
        raise ValidationError("Credits must be greater than zero.")

    if granted_at is None:
        granted_at = timezone.now()
    else:
        granted_at = _aware(granted_at)

    expires_at = _aware(expires_at)

    if expires_at <= granted_at:
        raise ValidationError("Expiry date must be after grant date.")

    pack = CreditPack.objects.create(
        member=member,
        granted_credits=credits,
        remaining_credits=credits,
        granted_at=granted_at,
        expires_at=expires_at,
    )
    pack.add_transaction(
        type=Transaction.TransactionType.CREDIT,
        description=Transaction.TransactionDescription.PACK_GRANT,
        amount=credits,
        created_at=granted_at,
    )
    return pack


def get_credit_balance(member, as_of=None):
    moment = _aware(as_of)
    packs = list(
        CreditPack.objects.filter(
            member=member,
            granted_at__lte=moment,
        ).order_by("expires_at", "granted_at", "id")
    )
    remaining = {pack.id: 0 for pack in packs}
    movements = Transaction.objects.filter(
        pack__member=member,
        created_at__lte=moment,
    ).order_by("created_at", "id")

    for movement in movements:
        if movement.pack_id not in remaining:
            continue
        if movement.type == Transaction.TransactionType.CREDIT:
            remaining[movement.pack_id] += movement.amount
        else:
            remaining[movement.pack_id] -= movement.amount

    pack_details = []
    total_credits = 0
    for pack in packs:
        if pack.expires_at <= moment:
            continue
        available = remaining.get(pack.id, 0)
        if available <= 0:
            continue
        pack_details.append(
            {
                "id": pack.id,
                "granted_credits": pack.granted_credits,
                "remaining_credits": available,
                "expires_at": pack.expires_at,
                "granted_at": pack.granted_at,
            }
        )
        total_credits += available

    return {
        "as_of": moment,
        "total_credits": total_credits,
        "packs": pack_details,
    }


def get_ledger(member, as_of=None):
    queryset = Transaction.objects.filter(pack__member=member).select_related(
        "pack",
        "booking",
        "booking__fitness_class",
    )
    if as_of is not None:
        queryset = queryset.filter(created_at__lte=_aware(as_of))
    return queryset.order_by("created_at", "id")


@transaction.atomic
def deduct_credits(member, booking, credits):  # noqa: C901
    if credits <= 0:
        raise ValidationError("Credits must be greater than zero.")
    try:
        booking = Booking.objects.select_for_update().get(
            pk=booking.pk,
            member=member,
        )
    except Booking.DoesNotExist as exc:
        raise ValidationError("Booking does not belong to this member.") from exc

    if booking.status != Booking.Status.CONFIRMED:
        raise ValidationError("Credits can only be deducted for confirmed bookings.")

    if Transaction.objects.filter(
        booking=booking,
        description=Transaction.TransactionDescription.BOOKING_CHARGE,
    ).exists():
        raise ValidationError("Credits have already been deducted for this booking.")

    now = timezone.now()
    remaining_to_deduct = credits

    packs = list(
        CreditPack.objects.select_for_update()
        .filter(
            member=member,
            expires_at__gt=now,
            remaining_credits__gt=0,
        )
        .order_by("expires_at", "granted_at", "pk")
    )

    total_available = sum(pack.remaining_credits for pack in packs)

    if total_available < credits:
        raise ValidationError("Insufficient credits.")

    for pack in packs:
        amount = min(
            pack.remaining_credits,
            remaining_to_deduct,
        )

        if amount <= 0:
            continue

        updated = CreditPack.objects.filter(
            pk=pack.pk,
            remaining_credits__gte=amount,
            expires_at__gt=now,
        ).update(
            remaining_credits=F("remaining_credits") - amount,
        )

        if updated != 1:
            raise ValidationError("Credit balance changed. Please try again.")

        pack.add_transaction(
            booking=booking,
            type=Transaction.TransactionType.DEBIT,
            description=Transaction.TransactionDescription.BOOKING_CHARGE,
            amount=amount,
        )

        remaining_to_deduct -= amount

        if remaining_to_deduct == 0:
            break

    if remaining_to_deduct:
        raise ValidationError("Insufficient credits.")

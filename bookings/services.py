from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from credits.models import CreditPack, Transaction
from credits.services import deduct_credits
from studios.models import FitnessClass

from .models import Booking, Slot


def _lock_class(fitness_class_id):
    try:
        return (
            FitnessClass.objects.select_for_update()
            .select_related("studio")
            .get(pk=fitness_class_id)
        )
    except FitnessClass.DoesNotExist as exc:
        raise ValidationError("Class not found.") from exc


def _require_future_class(fitness_class):
    if fitness_class.start_time <= timezone.now():
        raise ValidationError("Bookings are not available for started classes.")


def _active_booking(member, fitness_class):
    return Booking.objects.filter(
        member=member,
        fitness_class=fitness_class,
        status__in=[Booking.Status.CONFIRMED, Booking.Status.WAITING_LIST],
    ).first()


def _reserve_spot(fitness_class, booking):
    active_slot_numbers = set(
        Slot.objects.filter(fitness_class=fitness_class).values_list(
            "slot_number", flat=True
        )
    )
    if len(active_slot_numbers) >= fitness_class.spots:
        raise ValidationError("Class is full.")

    available_number = next(
        i for i in range(1, fitness_class.spots + 1) if i not in active_slot_numbers
    )
    slot = Slot.objects.create(
        fitness_class=fitness_class,
        booking=booking,
        slot_number=available_number,
    )
    FitnessClass.objects.filter(pk=fitness_class.pk).update(
        confirmed_count=len(active_slot_numbers) + 1
    )
    return slot


def _release_spot(fitness_class, booking):
    Slot.objects.filter(booking=booking).delete()
    remaining = Slot.objects.filter(fitness_class=fitness_class).count()
    FitnessClass.objects.filter(pk=fitness_class.pk).update(confirmed_count=remaining)


def _create_booking_row(
    member, fitness_class, status, idempotency_key, confirmed_at=None
):
    try:
        return Booking.objects.create(
            member=member,
            fitness_class=fitness_class,
            status=status,
            idempotency_key=idempotency_key,
            confirmed_at=confirmed_at,
        )
    except IntegrityError as exc:
        existing = Booking.objects.filter(
            member=member,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return existing
        raise ValidationError(
            "You already have an active booking for this class."
        ) from exc


@transaction.atomic
def create_booking(member, fitness_class_id, idempotency_key):
    if not idempotency_key or not str(idempotency_key).strip():
        raise ValidationError("Idempotency-Key header is required.")

    idempotency_key = str(idempotency_key).strip()
    fitness_class = _lock_class(fitness_class_id)

    existing_booking = Booking.objects.filter(
        member=member,
        idempotency_key=idempotency_key,
    ).first()
    if existing_booking:
        if existing_booking.fitness_class_id != fitness_class.id:
            raise ValidationError(
                "This Idempotency-Key was already used for another class."
            )
        return existing_booking

    if fitness_class.start_time <= timezone.now():
        raise ValidationError("Bookings are not available for started classes.")

    if _active_booking(member, fitness_class):
        raise ValidationError("You already have an active booking for this class.")

    active_slots_count = Slot.objects.filter(fitness_class=fitness_class).count()
    if active_slots_count < fitness_class.spots:
        booking = _create_booking_row(
            member,
            fitness_class,
            Booking.Status.CONFIRMED,
            idempotency_key,
            timezone.now(),
        )
        if booking.status != Booking.Status.CONFIRMED:
            return booking
        deduct_credits(
            member,
            booking,
            fitness_class.credit_cost,
        )
        _reserve_spot(fitness_class, booking)
        return booking

    return _create_booking_row(
        member,
        fitness_class,
        Booking.Status.WAITING_LIST,
        idempotency_key,
    )


@transaction.atomic
def cancel_booking(member, booking_id):
    try:
        booking = (
            Booking.objects.select_for_update()
            .select_related("fitness_class__studio")
            .get(pk=booking_id, member=member)
        )
    except Booking.DoesNotExist as exc:
        raise ValidationError("Booking not found.") from exc

    if booking.status == Booking.Status.CANCELLED:
        raise ValidationError("This booking has already been cancelled.")

    if booking.status not in [
        Booking.Status.CONFIRMED,
        Booking.Status.WAITING_LIST,
    ]:
        raise ValidationError("This booking cannot be cancelled.")

    now = timezone.now()
    was_confirmed = booking.status == Booking.Status.CONFIRMED
    fitness_class = _lock_class(booking.fitness_class_id)
    studio = fitness_class.studio
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = now
    booking.save(update_fields=["status", "cancelled_at"])

    if not was_confirmed:
        return booking

    _release_spot(fitness_class, booking)

    studio_tz = ZoneInfo(str(studio.timezone))
    class_start_local = fitness_class.start_time.astimezone(studio_tz)
    cutoff_local = class_start_local - timedelta(hours=studio.cancellation_cutoff_hours)
    now_local = now.astimezone(studio_tz)
    if now_local <= cutoff_local:
        _refund_booking_credits(booking)

    if fitness_class.start_time > now:
        _promote_waitlisted_member(fitness_class)
    return booking


def _refund_booking_credits(booking):
    charges = Transaction.objects.filter(
        booking=booking,
        type=Transaction.TransactionType.DEBIT,
        description=(Transaction.TransactionDescription.BOOKING_CHARGE),
    ).order_by("pack_id", "pk")

    for charge in charges:
        already_refunded = Transaction.objects.filter(
            booking=booking,
            pack_id=charge.pack_id,
            description=(Transaction.TransactionDescription.CANCELLATION_REFUND),
        ).exists()

        if already_refunded:
            continue

        pack = CreditPack.objects.select_for_update().get(
            pk=charge.pack_id,
        )
        pack.remaining_credits += charge.amount
        pack.save(update_fields=["remaining_credits"])
        pack.add_transaction(
            booking=booking,
            type=Transaction.TransactionType.CREDIT,
            description=Transaction.TransactionDescription.CANCELLATION_REFUND,
            amount=charge.amount,
        )


def _promote_waitlisted_member(fitness_class):
    if fitness_class.start_time <= timezone.now():
        return

    waiting_bookings = (
        Booking.objects.select_for_update()
        .filter(
            fitness_class=fitness_class,
            status=Booking.Status.WAITING_LIST,
        )
        .select_related("member")
        .order_by("booked_at", "id")
    )

    for waiting_booking in waiting_bookings:
        available_credits = (
            CreditPack.objects.filter(
                member=waiting_booking.member,
                expires_at__gt=timezone.now(),
                remaining_credits__gt=0,
            ).aggregate(total=Sum("remaining_credits"))["total"]
            or 0
        )
        if available_credits < fitness_class.credit_cost:
            continue

        waiting_booking.status = Booking.Status.CONFIRMED
        waiting_booking.confirmed_at = timezone.now()
        waiting_booking.save(update_fields=["status", "confirmed_at"])
        try:
            deduct_credits(
                waiting_booking.member,
                waiting_booking,
                fitness_class.credit_cost,
            )
            _reserve_spot(fitness_class, waiting_booking)
            return
        except ValidationError:
            waiting_booking.status = Booking.Status.WAITING_LIST
            waiting_booking.confirmed_at = None
            waiting_booking.save(update_fields=["status", "confirmed_at"])
            continue

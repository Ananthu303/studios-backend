from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from bookings.models import Booking
from bookings.services import cancel_booking, create_booking
from credits.services import grant_credit_pack
from studios.models import FitnessClass, Studio


class BookingsTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            phone_number="+919876500000",
            password="staffpassword123",
            role=User.Role.STAFF,
            is_staff=True,
        )
        self.member1 = User.objects.create_user(
            phone_number="+919876500001",
            password="memberpassword123",
            role=User.Role.MEMBER,
        )
        self.member2 = User.objects.create_user(
            phone_number="+919876500002",
            password="memberpassword123",
            role=User.Role.MEMBER,
        )
        self.member3 = User.objects.create_user(
            phone_number="+919876500003",
            password="memberpassword123",
            role=User.Role.MEMBER,
        )
        # Studio in New York (EDT/EST) with 4-hour cancellation cutoff
        self.studio = Studio.objects.create(
            name="Manhattan Studio",
            timezone="America/New_York",
            cancellation_cutoff_hours=4,
        )
        # Class with 1 spot, cost 2 credits, 24 hours in future
        self.fitness_class = FitnessClass.objects.create(
            studio=self.studio,
            name="Pilates Pro",
            start_time=timezone.now() + timedelta(hours=24),
            duration_minutes=50,
            spots=1,
            credit_cost=2,
        )
        # Grant credits to members
        self.pack1 = grant_credit_pack(
            member=self.member1,
            credits=10,
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.pack2 = grant_credit_pack(
            member=self.member2,
            credits=10,
            expires_at=timezone.now() + timedelta(days=30),
        )

    def test_book_class_success(self):
        self.client.force_authenticate(user=self.member1)
        url = reverse("booking-list")
        response = self.client.post(
            url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="key-book-1",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "CONFIRMED")

        # Class spots updated
        self.fitness_class.refresh_from_db()
        self.assertEqual(self.fitness_class.confirmed_count, 1)
        self.assertEqual(self.fitness_class.spots_available, 0)

        # Credits deducted
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

    def test_idempotency_key_replay(self):
        self.client.force_authenticate(user=self.member1)
        url = reverse("booking-list")

        resp1 = self.client.post(
            url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="idemp-key-dup",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Replay with same Idempotency-Key
        resp2 = self.client.post(
            url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="idemp-key-dup",
        )
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp1.data["id"], resp2.data["id"])

        # No double deduction
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

    def test_duplicate_booking_different_key_returns_400(self):
        self.client.force_authenticate(user=self.member1)
        url = reverse("booking-list")

        # First booking succeeds
        resp1 = self.client.post(
            url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="key-booking-first",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Second booking for same class with different key returns 400 Bad Request
        resp2 = self.client.post(
            url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="key-booking-second",
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already have an active booking", str(resp2.data))

    def test_insufficient_credits_fails(self):
        # Member 3 has 0 credits
        self.client.force_authenticate(user=self.member3)
        url = reverse("booking-list")
        response = self.client.post(
            url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="key-no-credits",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Booking.objects.filter(
                member=self.member3, fitness_class=self.fitness_class
            ).exists()
        )

    def test_class_full_waitlist_and_promotion_on_cancellation(self):
        # 1. Member 1 books the only spot
        booking1 = create_booking(
            member=self.member1,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="key-m1",
        )
        self.assertEqual(booking1.status, Booking.Status.CONFIRMED)

        # 2. Member 2 joins waitlist by booking full class
        self.client.force_authenticate(user=self.member2)
        booking_url = reverse("booking-list")
        resp_wl = self.client.post(
            booking_url,
            {"fitness_class": self.fitness_class.id},
            HTTP_IDEMPOTENCY_KEY="key-m2-wl",
        )
        self.assertEqual(resp_wl.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_wl.data["status"], "WAITING_LIST")

        # Member 2 is NOT charged while on waitlist
        self.pack2.refresh_from_db()
        self.assertEqual(self.pack2.remaining_credits, 10)

        # 3. Member 1 cancels booking before cutoff (class is 24h away, cutoff is 4h)
        cancel_booking(member=self.member1, booking_id=booking1.id)

        # Member 1 credits refunded
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 10)

        # Member 2 promoted to CONFIRMED and charged
        booking2 = Booking.objects.get(
            member=self.member2, fitness_class=self.fitness_class
        )
        self.assertEqual(booking2.status, Booking.Status.CONFIRMED)
        self.pack2.refresh_from_db()
        self.assertEqual(self.pack2.remaining_credits, 8)

    def test_cancellation_after_cutoff_forfeits_credits(self):
        # Class starts in 2 hours (less than 4 hours cutoff)
        late_class = FitnessClass.objects.create(
            studio=self.studio,
            name="Late Yoga",
            start_time=timezone.now() + timedelta(hours=2),
            duration_minutes=60,
            spots=2,
            credit_cost=2,
        )
        booking = create_booking(
            member=self.member1,
            fitness_class_id=late_class.id,
            idempotency_key="late-booking-key",
        )
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

        # Cancel after cutoff
        cancel_booking(member=self.member1, booking_id=booking.id)

        # Credits must be forfeited (NOT refunded)
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

    def test_repeated_cancellation_rejected(self):
        booking = create_booking(
            member=self.member1,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="cancel-repeat-key",
        )
        cancel_booking(member=self.member1, booking_id=booking.id)

        # Second cancellation must fail
        with self.assertRaises(Exception):
            cancel_booking(member=self.member1, booking_id=booking.id)

    def test_waitlist_skip_unaffordable_member_preserves_position(self):
        # Fill class
        create_booking(
            member=self.member1,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="fill-class-key",
        )

        # Member 3 (0 credits) joins waitlist first
        b_m3 = create_booking(
            member=self.member3,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="wl-m3",
        )
        # Member 2 (10 credits) joins waitlist second
        b_m2 = create_booking(
            member=self.member2,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="wl-m2",
        )

        # Member 1 cancels confirmed booking
        booking1 = Booking.objects.get(
            member=self.member1, fitness_class=self.fitness_class
        )
        cancel_booking(member=self.member1, booking_id=booking1.id)

        # Member 3 kept in WAITING_LIST (cannot afford)
        b_m3.refresh_from_db()
        self.assertEqual(b_m3.status, Booking.Status.WAITING_LIST)

        # Member 2 promoted to CONFIRMED (can afford)
        b_m2.refresh_from_db()
        self.assertEqual(b_m2.status, Booking.Status.CONFIRMED)
        self.pack2.refresh_from_db()
        self.assertEqual(self.pack2.remaining_credits, 8)

    def test_leave_waitlist(self):
        # Fill class
        create_booking(
            member=self.member1,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="fill-for-wl",
        )
        # Join waitlist
        wl_booking = create_booking(
            member=self.member2,
            fitness_class_id=self.fitness_class.id,
            idempotency_key="wl-to-leave",
        )

        self.client.force_authenticate(user=self.member2)
        leave_url = reverse("booking-detail", kwargs={"pk": wl_booking.id})
        response = self.client.delete(leave_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        wl_booking.refresh_from_db()
        self.assertEqual(wl_booking.status, Booking.Status.CANCELLED)

    def test_cutoff_measured_in_studio_local_time(self):
        ny_studio = Studio.objects.create(
            name="SoHo Pilates",
            timezone="America/New_York",
            cancellation_cutoff_hours=4,
        )
        ny_tz = ZoneInfo("America/New_York")

        # Class 1: Starts at 14:00 EDT (Cutoff is 10:00 EDT)
        class_1 = FitnessClass.objects.create(
            studio=ny_studio,
            name="Early Reformer",
            start_time=datetime(2026, 10, 25, 14, 0, 0, tzinfo=ny_tz),
            duration_minutes=50,
            spots=5,
            credit_cost=2,
        )

        # Member 1 books Class 1 (10 -> 8 credits)
        booking1 = create_booking(self.member1, class_1.id, "tz-test-key-1")
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

        # Cancel 1 minute before cutoff (09:59 EDT) -> Refunded in full
        before_cutoff = datetime(2026, 10, 25, 9, 59, 0, tzinfo=ny_tz)
        with patch("django.utils.timezone.now", return_value=before_cutoff):
            cancel_booking(self.member1, booking1.id)

        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 10)

        # Class 2: Starts at 12:00 EDT (Cutoff was 08:00 EDT)
        class_2 = FitnessClass.objects.create(
            studio=ny_studio,
            name="Late Reformer",
            start_time=datetime(2026, 10, 25, 12, 0, 0, tzinfo=ny_tz),
            duration_minutes=50,
            spots=5,
            credit_cost=2,
        )

        # Member 1 books Class 2 (10 -> 8 credits)
        booking2 = create_booking(self.member1, class_2.id, "tz-test-key-2")
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

        # Cancel 1 hour after cutoff (09:00 EDT) -> Forfeited
        after_cutoff = datetime(2026, 10, 25, 9, 0, 0, tzinfo=ny_tz)
        with patch("django.utils.timezone.now", return_value=after_cutoff):
            cancel_booking(self.member1, booking2.id)

        # Credits forfeited (remains 8)
        self.pack1.refresh_from_db()
        self.assertEqual(self.pack1.remaining_credits, 8)

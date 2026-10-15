from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from bookings.models import Booking
from credits.models import CreditPack, Transaction
from credits.services import deduct_credits, grant_credit_pack
from studios.models import FitnessClass, Studio


class CreditsTests(APITestCase):
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
        self.studio = Studio.objects.create(
            name="Downtown Studio",
            timezone="UTC",
            cancellation_cutoff_hours=4,
        )
        self.fitness_class = FitnessClass.objects.create(
            studio=self.studio,
            name="Cycling 101",
            start_time=timezone.now() + timedelta(days=2),
            duration_minutes=45,
            spots=10,
            credit_cost=3,
        )

    def test_staff_grant_credit_pack(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("credit-pack-list")
        expires_at = timezone.now() + timedelta(days=30)
        data = {
            "member": self.member1.id,
            "granted_credits": 10,
            "expires_at": expires_at.isoformat(),
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["granted_credits"], 10)
        self.assertEqual(response.data["remaining_credits"], 10)

        # Check ledger record
        tx = Transaction.objects.filter(pack__member=self.member1).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.type, Transaction.TransactionType.CREDIT)
        self.assertEqual(tx.description, Transaction.TransactionDescription.PACK_GRANT)
        self.assertEqual(tx.amount, 10)

    def test_pack_add_transaction_helper(self):
        pack = CreditPack.objects.create(
            member=self.member1,
            granted_credits=10,
            remaining_credits=10,
            expires_at=timezone.now() + timedelta(days=30),
        )
        tx = pack.add_transaction(
            type=Transaction.TransactionType.CREDIT,
            description=Transaction.TransactionDescription.PACK_GRANT,
            amount=10,
        )
        self.assertEqual(tx.pack, pack)
        self.assertEqual(tx.amount, 10)
        self.assertEqual(tx.type, Transaction.TransactionType.CREDIT)
        self.assertEqual(tx.description, Transaction.TransactionDescription.PACK_GRANT)

    def test_member_cannot_grant_pack(self):
        self.client.force_authenticate(user=self.member1)
        url = reverse("credit-pack-list")
        expires_at = timezone.now() + timedelta(days=30)
        data = {
            "member": self.member1.id,
            "granted_credits": 10,
            "expires_at": expires_at.isoformat(),
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fifo_credit_spending(self):
        now = timezone.now()
        # Pack 1 expires in 10 days (5 credits)
        pack1 = grant_credit_pack(
            member=self.member1,
            credits=5,
            expires_at=now + timedelta(days=10),
            granted_at=now - timedelta(days=2),
        )
        # Pack 2 expires in 5 days (5 credits) -> should be spent FIRST!
        pack2 = grant_credit_pack(
            member=self.member1,
            credits=5,
            expires_at=now + timedelta(days=5),
            granted_at=now - timedelta(days=1),
        )

        booking = Booking.objects.create(
            member=self.member1,
            fitness_class=self.fitness_class,
            status=Booking.Status.CONFIRMED,
        )

        # Spend 4 credits
        deduct_credits(member=self.member1, booking=booking, credits=4)

        pack1.refresh_from_db()
        pack2.refresh_from_db()

        # pack2 expires sooner, so all 4 credits should come from pack2
        self.assertEqual(pack2.remaining_credits, 1)
        self.assertEqual(pack1.remaining_credits, 5)

        # Spend another 3 credits (1 from pack2, 2 from pack1) on a second class
        class2 = FitnessClass.objects.create(
            studio=self.studio,
            name="Cycling 102",
            start_time=now + timedelta(days=3),
            duration_minutes=45,
            spots=10,
            credit_cost=3,
        )
        booking2 = Booking.objects.create(
            member=self.member1,
            fitness_class=class2,
            status=Booking.Status.CONFIRMED,
        )
        deduct_credits(member=self.member1, booking=booking2, credits=3)

        pack1.refresh_from_db()
        pack2.refresh_from_db()
        self.assertEqual(pack2.remaining_credits, 0)
        self.assertEqual(pack1.remaining_credits, 3)

    def test_expired_credits_cannot_be_spent(self):
        now = timezone.now()
        # Expired pack
        grant_credit_pack(
            member=self.member1,
            credits=10,
            expires_at=now - timedelta(seconds=1),
            granted_at=now - timedelta(days=10),
        )

        booking = Booking.objects.create(
            member=self.member1,
            fitness_class=self.fitness_class,
            status=Booking.Status.CONFIRMED,
        )

        with self.assertRaises(ValidationError):
            deduct_credits(member=self.member1, booking=booking, credits=5)

    def test_reconstruct_balance_at_past_moment(self):
        now = timezone.now()
        t0 = now - timedelta(days=10)
        t1 = now - timedelta(days=5)

        # Grant 10 credits at t0
        grant_credit_pack(
            member=self.member1,
            credits=10,
            expires_at=now + timedelta(days=20),
            granted_at=t0,
        )

        # Balance before t0 should be 0
        self.client.force_authenticate(user=self.member1)
        balance_url = reverse("credit-pack-balance")
        resp_before = self.client.get(
            balance_url,
            {"as_of": (t0 - timedelta(days=1)).isoformat()},
        )
        self.assertEqual(resp_before.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_before.data["total_credits"], 0)

        # Balance at t1 should be 10
        resp_t1 = self.client.get(balance_url, {"as_of": t1.isoformat()})
        self.assertEqual(resp_t1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_t1.data["total_credits"], 10)

    def test_member_isolation_on_credits(self):
        # Member 1 cannot read Member 2's balance
        self.client.force_authenticate(user=self.member1)
        balance_url = reverse("credit-pack-balance")
        response = self.client.get(balance_url, {"member": self.member2.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

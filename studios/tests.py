from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from studios.models import FitnessClass, Studio


class StudioTests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            phone_number="+919876500000",
            password="staffpassword123",
            role=User.Role.STAFF,
            is_staff=True,
        )
        self.member_user = User.objects.create_user(
            phone_number="+919876500001",
            password="memberpassword123",
            role=User.Role.MEMBER,
        )
        self.studio = Studio.objects.create(
            name="Downtown Studio",
            timezone="America/New_York",
            cancellation_cutoff_hours=6,
        )

    def test_studio_creation_by_staff(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("studio-list")
        data = {
            "name": "Westside Studio",
            "timezone": "Europe/London",
            "cancellation_cutoff_hours": 4,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Westside Studio")
        self.assertEqual(response.data["timezone"], "Europe/London")
        self.assertEqual(response.data["cancellation_cutoff_hours"], 4)

    def test_studio_creation_forbidden_for_member(self):
        self.client.force_authenticate(user=self.member_user)
        url = reverse("studio-list")
        data = {
            "name": "Hacker Studio",
            "timezone": "UTC",
            "cancellation_cutoff_hours": 2,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_timezone_rejected(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("studio-list")
        data = {
            "name": "Bad Timezone Studio",
            "timezone": "Mars/Olympus_Mons",
            "cancellation_cutoff_hours": 4,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_schedule_class_by_staff(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("fitness-class-list")
        start_time = timezone.now() + timedelta(days=2)
        data = {
            "studio": self.studio.id,
            "name": "Morning HIIT",
            "start_time": start_time.isoformat(),
            "duration_minutes": 45,
            "spots": 15,
            "credit_cost": 2,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["spots_available"], 15)

    def test_past_start_time_rejected(self):
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("fitness-class-list")
        start_time = timezone.now() - timedelta(hours=1)
        data = {
            "studio": self.studio.id,
            "name": "Past Yoga",
            "start_time": start_time.isoformat(),
            "duration_minutes": 60,
            "spots": 10,
            "credit_cost": 1,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_browse_classes_date_range_filter(self):
        now = timezone.now()
        class1 = FitnessClass.objects.create(
            studio=self.studio,
            name="Class Day 1",
            start_time=now + timedelta(days=1),
            duration_minutes=50,
            spots=10,
            credit_cost=1,
        )
        class2 = FitnessClass.objects.create(
            studio=self.studio,
            name="Class Day 5",
            start_time=now + timedelta(days=5),
            duration_minutes=50,
            spots=10,
            credit_cost=1,
        )

        self.client.force_authenticate(user=self.member_user)
        url = reverse("fitness-class-list")

        # Query range covering only day 1
        d1 = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        response = self.client.get(url, {"start_date": d1, "end_date": d1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data]
        self.assertIn(class1.id, ids)
        self.assertNotIn(class2.id, ids)

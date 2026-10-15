from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User


class AccountsTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            phone_number="+919876500000",
            password="adminpassword123",
        )
        self.staff_user = User.objects.create_user(
            phone_number="+919876500001",
            password="staffpassword123",
            role=User.Role.STAFF,
            is_staff=True,
        )
        self.member_user = User.objects.create_user(
            phone_number="+919876500002",
            password="memberpassword123",
            role=User.Role.MEMBER,
        )

    def test_member_registration(self):
        url = reverse("users-register")
        data = {
            "phone_number": "+919876500003",
            "password_1": "securepass123",
            "password_2": "securepass123",
            "role": "MEMBER",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(phone_number="+919876500003").exists())

    def test_superadmin_registration(self):
        url = reverse("users-register")
        data = {
            "phone_number": "+919876500098",
            "password_1": "securepass123",
            "password_2": "securepass123",
            "role": "SUPER_ADMIN",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "SUPER_ADMIN")
        user = User.objects.get(phone_number="+919876500098")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)


    def test_non_admin_cannot_register_staff(self):
        url = reverse("users-register")
        data = {
            "phone_number": "+919876500004",
            "password_1": "securepass123",
            "password_2": "securepass123",
            "role": "STAFF",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superadmin_can_register_staff(self):
        self.client.force_authenticate(user=self.superadmin)
        url = reverse("users-register")
        data = {
            "phone_number": "+919876500004",
            "password_1": "securepass123",
            "password_2": "securepass123",
            "role": "STAFF",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "STAFF")

    def test_login_and_token_refresh(self):
        login_url = reverse("users-login")
        response = self.client.post(
            login_url,
            {
                "phone_number": "+919876500002",
                "password": "memberpassword123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        refresh_token = response.data["refresh"]
        refresh_url = reverse("users-refresh-token")
        refresh_response = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

    def test_user_me_endpoint(self):
        self.client.force_authenticate(user=self.member_user)
        url = reverse("users-me")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], "+919876500002")

    def test_user_isolation(self):
        # Member can only see self in users list
        self.client.force_authenticate(user=self.member_user)
        list_url = reverse("users-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.member_user.id)

        # Staff can see all users
        self.client.force_authenticate(user=self.staff_user)
        staff_response = self.client.get(list_url)
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(staff_response.data), 3)

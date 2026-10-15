from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        STAFF = "STAFF", "Staff"
        SUPER_ADMIN = "SUPER_ADMIN", "Super admin"
        MEMBER = "MEMBER", "Member"

    phone_number = PhoneNumberField(unique=True)
    role = models.CharField(
        max_length=15,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    is_staff = models.BooleanField(
        "staff status",
        default=False,
        help_text="Designates whether the user can log into this admin site.",
    )
    is_active = models.BooleanField(
        "active",
        default=True,
        help_text=(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(
        "date joined",
        default=timezone.now,
    )
    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    objects = UserManager()  # type: ignore[assignment,misc]

    def __str__(self):
        return str(self.phone_number)

    @property
    def is_studio_staff(self):
        return self.role in (self.Role.STAFF, self.Role.SUPER_ADMIN)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

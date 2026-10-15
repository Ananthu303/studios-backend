from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from timezone_field import TimeZoneField

from accounts.models import TimeStampedModel


class Studio(TimeStampedModel):
    name = models.CharField(max_length=150)
    timezone = TimeZoneField(default="Asia/Kolkata")
    cancellation_cutoff_hours = models.PositiveSmallIntegerField(
        default=4,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(168),
        ],
    )

    def __str__(self):
        return self.name


class FitnessClass(TimeStampedModel):
    studio = models.ForeignKey(
        Studio,
        on_delete=models.CASCADE,
        related_name="classes",
    )
    name = models.CharField(max_length=150)
    start_time = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    spots = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    confirmed_count = models.PositiveSmallIntegerField(default=0)
    credit_cost = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["start_time"]

    @property
    def end_time(self):
        return self.start_time + timedelta(minutes=self.duration_minutes)

    @property
    def spots_available(self):
        return max(self.spots - self.confirmed_count, 0)

    @property
    def has_started(self):
        studio_tz = ZoneInfo(str(self.studio.timezone))
        return self.start_time.astimezone(studio_tz) <= timezone.now().astimezone(studio_tz)

    @property
    def is_within_cancellation_cutoff(self):
        studio_tz = ZoneInfo(str(self.studio.timezone))
        class_start = self.start_time.astimezone(studio_tz)
        cutoff = class_start - timedelta(hours=self.studio.cancellation_cutoff_hours)
        return timezone.now().astimezone(studio_tz) <= cutoff

    def __str__(self):
        return f"{self.name} - {self.start_time}"

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from accounts.models import TimeStampedModel
from timezone_field import TimeZoneField
from django.db.models import Q
from datetime import timedelta


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
    credit_cost = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=1),
                name="class_duration_positive",
            ),
            models.CheckConstraint(
                condition=Q(spots__gte=1),
                name="class_spots_positive",
            ),
            models.CheckConstraint(
                condition=Q(credit_cost__gte=1),
                name="class_credit_cost_positive",
            ),
        ]

    @property
    def end_time(self):
        return self.start_time + timedelta(minutes=self.duration_minutes)

    def __str__(self):
        return f"{self.name} - {self.start_time}"

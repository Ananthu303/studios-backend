from django.contrib import admin

from .models import FitnessClass, Studio


@admin.register(Studio)
class StudioAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "timezone", "cancellation_cutoff_hours")


@admin.register(FitnessClass)
class FitnessClassAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "studio",
        "start_time",
        "spots",
        "confirmed_count",
        "credit_cost",
    )
    list_filter = ("studio",)

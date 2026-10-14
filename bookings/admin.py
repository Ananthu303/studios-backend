from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "member",
        "fitness_class",
        "status",
        "booked_at",
        "cancelled_at",
    )
    list_filter = ("status",)
    search_fields = ("member__phone_number",)

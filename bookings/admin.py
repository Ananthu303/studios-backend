from django.contrib import admin

from .models import Booking, Slot


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

@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fitness_class",
        "slot_number",
        "booking",
        "created_at",
    )
    list_filter = ("fitness_class",)

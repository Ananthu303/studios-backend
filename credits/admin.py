from django.contrib import admin

from .models import CreditPack, Transaction


@admin.register(CreditPack)
class CreditPackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "member",
        "granted_credits",
        "remaining_credits",
        "granted_at",
        "expires_at",
    )


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pack",
        "type",
        "description",
        "amount",
        "booking",
        "created_at",
    )
    list_filter = ("type", "description")

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["CONFIRMED", "WAITING_LIST"])),
                fields=("member", "fitness_class"),
                name="unique_active_booking_per_member_class",
            ),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(
                fields=["fitness_class", "status", "booked_at"],
                name="booking_class_status_idx",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("credits", "0003_transaction_booking"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="creditpack",
            constraint=models.CheckConstraint(
                condition=models.Q(("remaining_credits__gte", 0)),
                name="credit_pack_remaining_gte_zero",
            ),
        ),
    ]

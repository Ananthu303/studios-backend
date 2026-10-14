import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("credits", "0004_creditpack_remaining_gte_zero"),
    ]

    operations = [
        migrations.AlterField(
            model_name="creditpack",
            name="granted_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="created_at",
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
    ]

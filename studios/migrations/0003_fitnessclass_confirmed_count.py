from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        ("studios", "0002_fitnessclass"),
    ]

    operations = [
        migrations.AddField(
            model_name="fitnessclass",
            name="confirmed_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="fitnessclass",
            constraint=models.CheckConstraint(
                condition=Q(confirmed_count__lte=F("spots")),
                name="class_confirmed_not_over_spots",
            ),
        ),
    ]

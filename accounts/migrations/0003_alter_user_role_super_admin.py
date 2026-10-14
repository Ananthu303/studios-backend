from django.db import migrations, models


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="SUPER ADMIN").update(role="SUPER_ADMIN")
    User.objects.filter(role="ADMIN").update(role="SUPER_ADMIN")


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="SUPER_ADMIN").update(role="SUPER ADMIN")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("STAFF", "Staff"),
                    ("SUPER_ADMIN", "Super admin"),
                    ("MEMBER", "Member"),
                ],
                default="MEMBER",
                max_length=15,
            ),
        ),
    ]

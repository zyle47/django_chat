from django.conf import settings
from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserProfile = apps.get_model("chat", "UserProfile")
    existing = set(UserProfile.objects.values_list("user_id", flat=True))
    missing_ids = User.objects.exclude(id__in=existing).values_list("id", flat=True)
    UserProfile.objects.bulk_create([UserProfile(user_id=uid) for uid in missing_ids])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0020_chatroom_creator_upgraderequest_userprofile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_missing_profiles, noop),
    ]

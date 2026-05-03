import hashlib

from django.db import migrations


def populate_public_id(apps, schema_editor):
    ChatRoom = apps.get_model("chat", "ChatRoom")
    for room in ChatRoom.objects.all():
        room.public_id = hashlib.sha256(room.name.encode()).hexdigest()
        room.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0014_chatroom_public_id"),
    ]

    operations = [
        migrations.RunPython(populate_public_id, migrations.RunPython.noop),
    ]

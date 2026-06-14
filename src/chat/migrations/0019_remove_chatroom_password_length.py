from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0018_friendblock"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="chatroom",
            name="password_length",
        ),
    ]

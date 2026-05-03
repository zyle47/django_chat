from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0010_chatroom_public_id_populate"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatroom",
            name="public_id",
            field=models.CharField(db_index=True, editable=False, max_length=64, unique=True),
        ),
    ]

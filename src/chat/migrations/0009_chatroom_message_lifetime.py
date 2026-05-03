from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0008_chatroom_password_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatroom',
            name='message_lifetime',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]

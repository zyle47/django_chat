from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0012_dmread'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatimage',
            name='caption',
            field=models.CharField(blank=True, default='', max_length=1000),
        ),
    ]

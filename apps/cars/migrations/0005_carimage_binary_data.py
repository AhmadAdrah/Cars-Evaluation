from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0004_favoritecar'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='carimage',
            name='image',
        ),
        migrations.AddField(
            model_name='carimage',
            name='content_type',
            field=models.CharField(default='image/jpeg', max_length=100),
        ),
        migrations.AddField(
            model_name='carimage',
            name='image_data',
            field=models.BinaryField(default=b''),
            preserve_default=False,
        ),
    ]

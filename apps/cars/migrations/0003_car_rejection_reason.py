from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0002_alter_car_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='car',
            name='rejection_reason',
            field=models.CharField(blank=True, help_text='Reason entered by an admin when rejecting this listing', max_length=500, null=True),
        ),
    ]

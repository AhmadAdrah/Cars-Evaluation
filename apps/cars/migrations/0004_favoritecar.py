import django.utils.timezone
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_name_user_phone_number'),
        ('cars', '0003_car_rejection_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriteCar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('car', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorited_by', to='cars.car')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorite_cars', to='accounts.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('user', 'car')},
            },
        ),
    ]

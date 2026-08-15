from django.conf import settings
from django.db import models
from django.utils import timezone


class Car(models.Model):
    class FuelType(models.TextChoices):
        GASOLINE = 'Gasoline', 'Gasoline'
        PLUG_IN_HYBRID = 'Plug-In Hybrid', 'Plug-In Hybrid'
        HYBRID = 'Hybrid', 'Hybrid'
        DIESEL = 'Diesel', 'Diesel'

    class Transmission(models.TextChoices):
        AUTOMATIC = 'Automatic', 'Automatic'
        MANUAL = 'Manual', 'Manual'

    class AccidentStatus(models.TextChoices):
        CLEAN = 'Clean', 'Clean'
        ACCIDENT_REPORTED = 'Accident Reported', 'Accident Reported'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        AVAILABLE = 'AVAILABLE', 'Available'
        REJECTED = 'REJECTED', 'Rejected'
        SOLD = 'SOLD', 'Sold'

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cars',
    )
    brand = models.CharField(max_length=50)
    base_model = models.CharField(max_length=100)
    model_year = models.PositiveIntegerField()
    fuel_type = models.CharField(max_length=30, choices=FuelType.choices, default=FuelType.GASOLINE)
    transmission = models.CharField(max_length=20, choices=Transmission.choices, default=Transmission.AUTOMATIC)
    ext_col = models.CharField(max_length=50, help_text='Exterior color')
    accident = models.CharField(max_length=30, choices=AccidentStatus.choices, default=AccidentStatus.CLEAN)
    country_of_origin = models.CharField(max_length=50)
    engine_cc = models.PositiveIntegerField(help_text='Engine capacity in cc')
    mileage_km = models.PositiveIntegerField(help_text='Mileage in kilometers')
    description = models.TextField(blank=True)
    price_usd = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_price_usd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Predicted price computed by the evaluation model',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.brand} {self.base_model} ({self.model_year})'


class CarImage(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='cars/%Y/%m/%d/')
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-is_primary', 'uploaded_at']

    def __str__(self) -> str:
        return f'{self.car} - {self.image.name}'

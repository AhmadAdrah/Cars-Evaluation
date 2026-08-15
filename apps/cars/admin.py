from django.contrib import admin

from .models import Car, CarImage


class CarImageInline(admin.TabularInline):
    model = CarImage
    extra = 1


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = [
        'brand', 'base_model', 'model_year', 'fuel_type', 'transmission',
        'mileage_km', 'price_usd', 'status', 'seller', 'created_at',
    ]
    list_filter = ['brand', 'fuel_type', 'transmission', 'accident', 'status', 'model_year']
    search_fields = ['brand', 'base_model', 'country_of_origin', 'ext_col']
    inlines = [CarImageInline]
    readonly_fields = ['estimated_price_usd', 'created_at', 'updated_at']


@admin.register(CarImage)
class CarImageAdmin(admin.ModelAdmin):
    list_display = ['car', 'image', 'is_primary', 'uploaded_at']
    list_filter = ['is_primary']
    search_fields = ['car__brand', 'car__base_model']

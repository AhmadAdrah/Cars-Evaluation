from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.cars.models import BannerImage, Car, CarImage, FavoriteCar


class CarImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = CarImage
        fields = ['id', 'image', 'is_primary', 'uploaded_at']

    def get_image(self, obj) -> str | None:
        if not obj.image_data:
            return None
        return reverse('cars-image', kwargs={'pk': obj.pk})


class BannerImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = BannerImage
        fields = ['id', 'image', 'is_active', 'sort_order', 'created_at']

    def get_image(self, obj) -> str | None:
        if not obj.image_data:
            return None
        return reverse('cars-banner-image', kwargs={'pk': obj.pk})


class CarSerializer(serializers.ModelSerializer):
    images = CarImageSerializer(many=True, read_only=True)
    seller_email = serializers.EmailField(source='seller.email', read_only=True)
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Car
        fields = [
            'id',
            'seller',
            'seller_email',
            'brand',
            'base_model',
            'model_year',
            'fuel_type',
            'transmission',
            'ext_col',
            'accident',
            'country_of_origin',
            'engine_cc',
            'mileage_km',
            'description',
            'price_usd',
            'estimated_price_usd',
            'status',
            'rejection_reason',
            'is_favorited',
            'images',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'seller',
            'estimated_price_usd',
            'status',
            'rejection_reason',
            'is_favorited',
            'images',
            'created_at',
            'updated_at',
        ]

    def get_is_favorited(self, obj) -> bool:
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return False
        annotated = getattr(obj, 'is_favorited_annotated', None)
        if annotated is not None:
            return bool(annotated)
        return FavoriteCar.objects.filter(user=user, car=obj).exists()


class CarCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Car
        fields = [
            'brand',
            'base_model',
            'model_year',
            'fuel_type',
            'transmission',
            'ext_col',
            'accident',
            'country_of_origin',
            'engine_cc',
            'mileage_km',
            'description',
            'price_usd',
        ]

    def validate_price_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError('Price must be greater than zero.')
        return value


class CarUpdateSerializer(CarCreateSerializer):
    """Editable car fields for seller updates (same as create, used with partial=True)."""

    pass


class AdminUserSerializer(serializers.ModelSerializer):
    cars_count = serializers.IntegerField(source='cars.count', read_only=True)
    available_cars_count = serializers.SerializerMethodField()
    pending_cars_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'name',
            'email',
            'phone_number',
            'role',
            'is_active',
            'is_staff',
            'date_joined',
            'can_sell_cars',
            'can_rate_cars',
            'can_buy_cars',
            'cars_count',
            'available_cars_count',
            'pending_cars_count',
        ]

    def get_available_cars_count(self, obj):
        return obj.cars.filter(status=Car.Status.AVAILABLE).count()

    def get_pending_cars_count(self, obj):
        return obj.cars.filter(status=Car.Status.PENDING).count()
from rest_framework import serializers

from apps.accounts.models import User
from apps.cars.models import Car, CarImage


class CarImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarImage
        fields = ['id', 'image', 'is_primary', 'uploaded_at']


class CarImageCreateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=True,
    )

    class Meta:
        model = CarImage
        fields = ['is_primary', 'images']

    def validate_images(self, value):
        if not value:
            raise serializers.ValidationError('At least one image is required.')
        return value


class CarSerializer(serializers.ModelSerializer):
    images = CarImageSerializer(many=True, read_only=True)
    seller_email = serializers.EmailField(source='seller.email', read_only=True)

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
            'images',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'seller',
            'estimated_price_usd',
            'status',
            'images',
            'created_at',
            'updated_at',
        ]


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
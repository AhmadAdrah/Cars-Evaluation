from django.db import transaction
from django.db.models import Avg, Count, Exists, Max, Min, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.cars.models import BannerImage, Car, CarImage, FavoriteCar
from apps.cars.services.car_image_service import (
    ImageValidationError,
    attach_car_images,
    compress_image,
    validate_uploaded_images,
)
from apps.cars.services.metadata_service import get_all_brands, get_base_models_for_brand
from apps.cars.services.pagination_service import paginate_queryset
from apps.cars.services.price_prediction_service import predict_price_from_request
from apps.cars.services.recommendation_service import recommend_similar_cars
from apps.cars.services.text_sanitization_service import sanitize_description

from .serializers import (
    AdminUserSerializer,
    BannerImageSerializer,
    CarCreateSerializer,
    CarImageSerializer,
    CarSerializer,
    CarUpdateSerializer,
)


class PredictCarPriceAPIView(APIView):
    """Estimate used car price using the trained XGBoost model."""

    def post(self, request, *args, **kwargs):
        payload = request.data or {}

        try:
            confidence = float(payload.get('confidence', 0.90))
            margin_percent = payload.get('margin_percent')
            result = predict_price_from_request(payload, confidence=confidence, margin_percent=margin_percent)
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ModuleNotFoundError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as exc:  # pragma: no cover
            return Response({'detail': f'Prediction failed: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SellerAddCarAPIView(APIView):
    """Seller adds a car listing — price is validated against the model's logical range."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not request.user.can_sell_cars:
            return Response(
                {'detail': 'Your account is not allowed to sell cars.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CarCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            image_files = validate_uploaded_images(request.FILES.getlist('images'))
        except ImageValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        car_data = serializer.validated_data
        prediction_payload = {
            'brand': car_data['brand'],
            'model_year': car_data['model_year'],
            'fuel_type': car_data['fuel_type'],
            'transmission': car_data['transmission'],
            'ext_col': car_data['ext_col'],
            'accident': car_data['accident'],
            'country_of_origin': car_data['country_of_origin'],
            'engine_cc': car_data['engine_cc'],
            'mileage_km': car_data['mileage_km'],
            'base_model': car_data['base_model'],
        }

        prediction = predict_price_from_request(prediction_payload)

        submitted_price = float(car_data['price_usd'])
        price_range = prediction['price_range']
        min_price = price_range['min_price_usd']
        max_price = price_range['max_price_usd']
        is_within_range = min_price <= submitted_price <= max_price

        if not is_within_range:
            return Response(
                {
                    'detail': (
                        f'The submitted price ${submitted_price:,.0f} is outside the logical range '
                        f'(${min_price:,.0f} – ${max_price:,.0f}). '
                        'Please adjust the price and resubmit.'
                    ),
                    'predicted_price_usd': prediction['predicted_price_usd'],
                    'price_range': prediction['price_range'],
                    'submitted_price_usd': submitted_price,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        sanitized = sanitize_description(car_data.get('description', ''))
        with transaction.atomic():
            car = serializer.save(
                seller=request.user,
                estimated_price_usd=prediction['predicted_price_usd'],
                description=sanitized['text'],
                status=Car.Status.PENDING,
            )
            attach_car_images(car, image_files)

        return Response(
            {
                'detail': 'Car submitted successfully and is pending admin approval.',
                'car': CarSerializer(car).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminApproveCarAPIView(APIView):
    """Admin approves a pending car listing, making it publicly available."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk)

        if car.status != Car.Status.PENDING:
            return Response(
                {'detail': f'Car is already {car.status.lower()}. Only pending cars can be approved.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        car.status = Car.Status.AVAILABLE
        car.rejection_reason = None
        car.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return Response({'detail': 'Car approved and published.', 'car': CarSerializer(car).data})


class AdminRejectCarAPIView(APIView):
    """Admin rejects a pending car listing, optionally with a reason for the seller."""

    MAX_REASON_LENGTH = 500

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk)

        if car.status != Car.Status.PENDING:
            return Response(
                {'detail': f'Car is already {car.status.lower()}. Only pending cars can be rejected.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = (request.data or {}).get('reason', '')
        reason = sanitize_description(str(reason))['text'][: self.MAX_REASON_LENGTH]

        car.status = Car.Status.REJECTED
        car.rejection_reason = reason or None
        car.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        return Response({'detail': 'Car rejected.', 'car': CarSerializer(car).data})


class AdminMarkSoldCarAPIView(APIView):
    """Admin marks an available car as sold."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk)

        if car.status != Car.Status.AVAILABLE:
            return Response(
                {'detail': f'Car is currently {car.status.lower()}. Only available cars can be marked as sold.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        car.status = Car.Status.SOLD
        car.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Car marked as sold.', 'car': CarSerializer(car).data})


class AdminDeleteCarAPIView(APIView):
    """Admin permanently deletes a car listing."""

    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk)
        car.delete()
        return Response({'detail': 'Car deleted.'}, status=status.HTTP_200_OK)


class AdminPendingCarsAPIView(APIView):
    """Admin: list all cars awaiting approval (status=PENDING) for the review queue."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        cars = Car.objects.filter(status=Car.Status.PENDING).select_related('seller').prefetch_related('images').order_by('created_at')
        return Response(paginate_queryset(request, cars, CarSerializer), status=status.HTTP_200_OK)


class AdminAllCarsAPIView(APIView):
    """Admin: dashboard listing of all cars with status and attribute filters."""

    FILTERABLE = {
        'brand': 'icontains',
        'base_model': 'icontains',
        'model_year': 'exact',
        'fuel_type': 'iexact',
        'transmission': 'iexact',
        'ext_col': 'icontains',
        'accident': 'iexact',
        'country_of_origin': 'icontains',
        'engine_cc': 'exact',
        'mileage_km': 'exact',
    }
    ORDERABLE = {'price_usd', 'model_year', 'mileage_km', 'engine_cc', 'created_at', 'updated_at'}

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        cars = Car.objects.select_related('seller').prefetch_related('images').all()

        status_filter = request.query_params.get('status')
        if status_filter:
            cars = cars.filter(status=status_filter)

        for field, lookup in self.FILTERABLE.items():
            value = request.query_params.get(field)
            if not value:
                continue
            cars = cars.filter(**{f'{field}__{lookup}': value})

        min_price = self._safe_decimal(request.query_params.get('min_price'))
        max_price = self._safe_decimal(request.query_params.get('max_price'))
        if min_price is not None:
            cars = cars.filter(price_usd__gte=min_price)
        if max_price is not None:
            cars = cars.filter(price_usd__lte=max_price)

        order_by = request.query_params.get('ordering')
        if order_by and order_by.lstrip('-') in self.ORDERABLE:
            cars = cars.order_by(order_by)

        return Response(paginate_queryset(request, cars, CarSerializer), status=status.HTTP_200_OK)

    @staticmethod
    def _safe_decimal(value):
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class AdminDashboardStatsAPIView(APIView):
    """Admin: aggregate statistics about cars and users for the dashboard."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        cars = Car.objects.all()
        available_cars = cars.filter(status=Car.Status.AVAILABLE)

        total_cars = cars.count()
        status_counts = {
            status: cars.filter(status=status).count()
            for status in Car.Status.values
        }

        price_stats = available_cars.aggregate(
            avg_price=Avg('price_usd'),
            min_price=Min('price_usd'),
            max_price=Max('price_usd'),
        )
        mileage_stats = available_cars.aggregate(
            avg_mileage_km=Avg('mileage_km'),
        )
        year_stats = available_cars.aggregate(
            avg_model_year=Avg('model_year'),
        )

        users = User.objects.all().exclude(role=User.Role.ADMIN)
        total_users = users.count()
        active_users = users.filter(is_active=True).count()
        sellers = users.filter(can_sell_cars=True).count()
        buyers = users.filter(can_buy_cars=True).count()
        raters = users.filter(can_rate_cars=True).count()

        images_count = CarImage.objects.count()
        brands_count = cars.values('brand').distinct().count()
        base_models_count = cars.values('brand', 'base_model').distinct().count()

        return Response(
            {
                'cars': {
                    'total': total_cars,
                    'by_status': status_counts,
                    'available': status_counts.get(Car.Status.AVAILABLE, 0),
                    'pending_approval': status_counts.get(Car.Status.PENDING, 0),
                    'brands_count': brands_count,
                    'base_models_count': base_models_count,
                    'images_count': images_count,
                },
                'car_averages': {
                    'avg_price_usd': round(float(price_stats['avg_price']), 2) if price_stats['avg_price'] is not None else None,
                    'min_price_usd': round(float(price_stats['min_price']), 2) if price_stats['min_price'] is not None else None,
                    'max_price_usd': round(float(price_stats['max_price']), 2) if price_stats['max_price'] is not None else None,
                    'avg_mileage_km': round(float(mileage_stats['avg_mileage_km']), 1) if mileage_stats['avg_mileage_km'] is not None else None,
                    'avg_model_year': round(float(year_stats['avg_model_year']), 1) if year_stats['avg_model_year'] is not None else None,
                },
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'sellers': sellers,
                    'buyers': buyers,
                    'raters': raters,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminCarDetailAPIView(APIView):
    """Admin: get full details of any car regardless of status, including the seller."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car.objects.select_related('seller').prefetch_related('images'), pk=pk)
        return Response(CarSerializer(car).data, status=status.HTTP_200_OK)


class AdminUserListAPIView(APIView):
    """Admin: list all users with their profile info and car counts."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        users = User.objects.annotate(cars_count=Count('cars')).order_by('-date_joined')

        role = request.query_params.get('role')
        if role:
            users = users.filter(role=role)

        active = request.query_params.get('active')
        if active is not None:
            users = users.filter(is_active=active.lower() in ('1', 'true', 'yes'))

        return Response(paginate_queryset(request, users, AdminUserSerializer), status=status.HTTP_200_OK)


class AdminUserCarsAPIView(APIView):
    """Admin: list all cars belonging to a specific user."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, user_id, *args, **kwargs):
        user = get_object_or_404(User, pk=user_id)
        cars = Car.objects.filter(seller=user).select_related('seller').prefetch_related('images')

        status_filter = request.query_params.get('status')
        if status_filter:
            cars = cars.filter(status=status_filter)

        page_data = paginate_queryset(request, cars, CarSerializer)
        page_data['user'] = AdminUserSerializer(user).data
        return Response(page_data, status=status.HTTP_200_OK)


class CarListAPIView(APIView):
    """Buyer: list approved cars only, with filters on all attributes and price range."""

    FILTERABLE = {
        'brand': 'icontains',
        'base_model': 'icontains',
        'model_year': 'exact',
        'fuel_type': 'iexact',
        'transmission': 'iexact',
        'ext_col': 'icontains',
        'accident': 'iexact',
        'country_of_origin': 'icontains',
        'engine_cc': 'exact',
        'mileage_km': 'exact',
    }

    permission_classes = [permissions.AllowAny]

    @classmethod
    def _favorite_annotation(cls, request):
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return Exists(
                FavoriteCar.objects.filter(user=user, car=OuterRef('pk')),
            )
        return None

    def get(self, request, *args, **kwargs):
        cars = Car.objects.filter(status=Car.Status.AVAILABLE).select_related('seller').prefetch_related('images')

        favorite_flag = self._favorite_annotation(request)
        if favorite_flag is not None:
            cars = cars.annotate(is_favorited_annotated=favorite_flag)

        for field, lookup in self.FILTERABLE.items():
            value = request.query_params.get(field)
            if not value:
                continue
            cars = cars.filter(**{f'{field}__{lookup}': value})

        min_price = self._safe_decimal(request.query_params.get('min_price'))
        max_price = self._safe_decimal(request.query_params.get('max_price'))
        if min_price is not None:
            cars = cars.filter(price_usd__gte=min_price)
        if max_price is not None:
            cars = cars.filter(price_usd__lte=max_price)

        order_by = request.query_params.get('ordering')
        if order_by and order_by.lstrip('-') in {
            'price_usd', 'model_year', 'mileage_km', 'engine_cc', 'created_at',
        }:
            cars = cars.order_by(order_by)

        return Response(paginate_queryset(request, cars, CarSerializer), status=status.HTTP_200_OK)

    @staticmethod
    def _safe_decimal(value):
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class BuyerCarDetailAPIView(APIView):
    """Buyer: get details of an approved car, with similar-content recommendations."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk, status=Car.Status.AVAILABLE)

        favorite_flag = CarListAPIView._favorite_annotation(request)
        if favorite_flag is not None:
            car = Car.objects.filter(pk=car.pk).annotate(is_favorited_annotated=favorite_flag).first()

        limit = int(request.query_params.get('limit', 6))
        if limit < 1:
            limit = 1
        if limit > 20:
            limit = 20

        similar_cars = recommend_similar_cars(car, limit=limit)
        context = {'request': request}

        return Response(
            {
                'car': CarSerializer(car, context=context).data,
                'similar_cars': CarSerializer(similar_cars, many=True, context=context).data,
            },
            status=status.HTTP_200_OK,
        )


class ToggleFavoriteAPIView(APIView):
    """Authenticated user: add/remove a car from favorites (toggle)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk, status=Car.Status.AVAILABLE)

        favorite, created = FavoriteCar.objects.get_or_create(user=request.user, car=car)
        if not created:
            favorite.delete()
            return Response(
                {
                    'detail': 'Removed from favorites.',
                    'is_favorited': False,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                'detail': 'Added to favorites.',
                'is_favorited': True,
            },
            status=status.HTTP_201_CREATED,
        )


class FavoriteCarsListAPIView(APIView):
    """Authenticated user: list the user's favorite available cars."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        cars = (
            Car.objects.filter(
                status=Car.Status.AVAILABLE,
                favorited_by__user=request.user,
            )
            .select_related('seller')
            .prefetch_related('images')
            .annotate(is_favorited_annotated=Exists(
                FavoriteCar.objects.filter(user=request.user, car=OuterRef('pk')),
            ))
            .order_by('-favorited_by__created_at')
        )
        return Response(paginate_queryset(request, cars, CarSerializer), status=status.HTTP_200_OK)


class SellerCarsAPIView(APIView):
    """Seller: list the authenticated seller's own cars (approved + pending + rejected)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        cars = Car.objects.filter(seller=request.user).select_related('seller').prefetch_related('images')
        status_filter = request.query_params.get('status')
        if status_filter:
            cars = cars.filter(status=status_filter)
        return Response(paginate_queryset(request, cars, CarSerializer))


class SellerCarDetailAPIView(APIView):
    """Seller: get details of one of the seller's own cars (any status)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car.objects.prefetch_related('images'), pk=pk, seller=request.user)
        return Response(CarSerializer(car).data)

    def patch(self, request, pk, *args, **kwargs):
        return self._update_car(request, pk, partial=True)

    def put(self, request, pk, *args, **kwargs):
        return self._update_car(request, pk, partial=False)

    def _update_car(self, request, pk, partial):
        car = get_object_or_404(Car, pk=pk, seller=request.user)

        serializer = CarUpdateSerializer(car, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = dict(serializer.validated_data)

        try:
            image_files = validate_uploaded_images(request.FILES.getlist('images'))
        except ImageValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        prediction_payload = {
            'brand': updated.get('brand', car.brand),
            'model_year': updated.get('model_year', car.model_year),
            'fuel_type': updated.get('fuel_type', car.fuel_type),
            'transmission': updated.get('transmission', car.transmission),
            'ext_col': updated.get('ext_col', car.ext_col),
            'accident': updated.get('accident', car.accident),
            'country_of_origin': updated.get('country_of_origin', car.country_of_origin),
            'engine_cc': updated.get('engine_cc', car.engine_cc),
            'mileage_km': updated.get('mileage_km', car.mileage_km),
            'base_model': updated.get('base_model', car.base_model),
        }

        prediction = predict_price_from_request(prediction_payload)

        submitted_price = float(updated.get('price_usd', car.price_usd))
        price_range = prediction['price_range']
        min_price = price_range['min_price_usd']
        max_price = price_range['max_price_usd']
        is_within_range = min_price <= submitted_price <= max_price

        if not is_within_range:
            return Response(
                {
                    'detail': (
                        f'The submitted price ${submitted_price:,.0f} is outside the logical range '
                        f'(${min_price:,.0f} – ${max_price:,.0f}). '
                        'Please adjust the price and resubmit.'
                    ),
                    'predicted_price_usd': prediction['predicted_price_usd'],
                    'price_range': prediction['price_range'],
                    'submitted_price_usd': submitted_price,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        updated['estimated_price_usd'] = prediction['predicted_price_usd']

        if 'description' in updated:
            updated['description'] = sanitize_description(updated['description'])['text']

        if updated:
            updated['status'] = Car.Status.PENDING

        with transaction.atomic():
            car = serializer.save(**updated)
            attach_car_images(car, image_files)

        return Response(
            {
                'detail': 'Car updated successfully. The listing is pending admin approval again.',
                'car': CarSerializer(car).data,
            },
            status=status.HTTP_200_OK,
        )


class SellerDeleteCarAPIView(APIView):
    """Seller permanently deletes one of the seller's own cars."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk, seller=request.user)
        car.delete()
        return Response({'detail': 'Car deleted.'}, status=status.HTTP_200_OK)


class AddCarImagesAPIView(APIView):
    """Seller: add one or more images to one of the seller's own cars."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        car = get_object_or_404(Car, pk=pk, seller=request.user)

        files = request.FILES.getlist('images')
        if not files:
            return Response(
                {'detail': 'No image files were provided. Send at least one file with field name "images".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            files = validate_uploaded_images(files)
        except ImageValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        images = attach_car_images(car, files)

        return Response(
            {
                'detail': f'{len(images)} image(s) added to car.',
                'images': CarImageSerializer(images, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CarImageAPIView(APIView):
    """Serve an image stored in the database as its original binary bytes."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, pk, *args, **kwargs):
        image = get_object_or_404(CarImage, pk=pk)
        if not image.image_data:
            return Response({'detail': 'Image data is empty.'}, status=status.HTTP_404_NOT_FOUND)
        return HttpResponse(image.image_data, content_type=image.content_type)


class BannerListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        banners = BannerImage.objects.filter(is_active=True)
        return Response(BannerImageSerializer(banners, many=True).data, status=status.HTTP_200_OK)


class BannerImageAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk, *args, **kwargs):
        banner = get_object_or_404(BannerImage, pk=pk, is_active=True)
        if not banner.image_data:
            return Response({'detail': 'Image data is empty.'}, status=status.HTTP_404_NOT_FOUND)
        return HttpResponse(banner.image_data, content_type=banner.content_type)


class AdminBannerListAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        banners = BannerImage.objects.all()
        return Response(BannerImageSerializer(banners, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        image_file = request.FILES.get('image')
        if image_file is None:
            return Response({'detail': 'An image is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_uploaded_images([image_file])
            image_data, content_type = compress_image(image_file)
        except ImageValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        banner = BannerImage.objects.create(
            image_data=image_data,
            content_type=content_type,
            sort_order=BannerImage.objects.count(),
        )
        return Response(BannerImageSerializer(banner).data, status=status.HTTP_201_CREATED)


class AdminBannerDetailAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, pk, *args, **kwargs):
        banner = get_object_or_404(BannerImage, pk=pk)
        banner.delete()
        return Response({'detail': 'Banner deleted.'}, status=status.HTTP_200_OK)


class BrandListAPIView(APIView):
    """Public: list all brands available in the training dataset."""

    def get(self, request, *args, **kwargs):
        brands = get_all_brands()
        return Response(
            {'count': len(brands), 'brands': brands},
            status=status.HTTP_200_OK,
        )


class BaseModelListAPIView(APIView):
    """Public: list all base models for a given brand."""

    def get(self, request, brand, *args, **kwargs):
        brand_clean = brand.strip()
        if not brand_clean:
            return Response({'detail': 'Brand is required.'}, status=status.HTTP_400_BAD_REQUEST)

        models = get_base_models_for_brand(brand_clean)

        if request.GET.get('validate') is not None:
            return Response(
                {'brand': brand_clean, 'exists': len(models) > 0, 'base_models': models},
                status=status.HTTP_200_OK,
            )

        return Response(
            {'brand': brand_clean, 'count': len(models), 'base_models': models},
            status=status.HTTP_200_OK,
        )
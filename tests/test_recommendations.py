from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.cars.models import Car
from apps.cars.services.price_prediction_service import predict_price_from_request
from apps.cars.services.recommendation_service import recommend_similar_cars

User = get_user_model()

CREATE_URL = '/api/cars/create/'
DETAIL_URL = '/api/cars/{pk}/'

CAR_BASE_DATA = {
    'brand': 'Toyota',
    'base_model': 'Corolla',
    'model_year': 2019,
    'fuel_type': 'Gasoline',
    'transmission': 'Automatic',
    'ext_col': 'Black',
    'accident': 'Clean',
    'country_of_origin': 'Japan',
    'engine_cc': 1800,
    'mileage_km': 60000,
}


def car_data(**overrides):
    data = {**CAR_BASE_DATA, **overrides}
    prediction = predict_price_from_request(data)
    low = float(prediction['price_range']['min_price_usd'])
    high = float(prediction['price_range']['max_price_usd'])
    data['price_usd'] = round((low + high) / 2, 2)
    return data


class RecommendationsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.seller = User.objects.create_user(email='rec-seller@example.com', password='StrongPass123!')
        self.admin = User.objects.create_superuser(email='rec-admin@example.com', password='Admin123!')

        self.client.force_authenticate(self.seller)
        created = self.client.post(CREATE_URL, car_data(), format="json")
        self.reference_id = created.data['car']['id']
        self.client.force_authenticate(self.admin); self.client.post(f'/api/cars/{self.reference_id}/approve/')

        for i, brand in enumerate(['Toyota', 'Toyota', 'BMW']):
            data = car_data(
                brand=brand,
                base_model='Corolla' if brand == 'Toyota' else 'X5',
                mileage_km=60000 + (i * 1000),
            )
            made = self.client.post(CREATE_URL, data, format='json')
            self.client.force_authenticate(self.admin); self.client.post(f"/api/cars/{made.data['car']['id']}/approve/")
            self.client.force_authenticate(self.seller)

    def test_detail_returns_similar_cars_with_toyota_ranked_first(self):
        self.client.force_authenticate(None)
        response = self.client.get(DETAIL_URL.format(pk=self.reference_id))

        self.assertEqual(response.status_code, 200)
        similar = response.data['similar_cars']
        self.assertTrue(similar)
        self.assertEqual(similar[0]['brand'], 'Toyota')

    def test_limit_is_clamped(self):
        car = Car.objects.get(pk=self.reference_id)
        self.assertLessEqual(len(recommend_similar_cars(car, limit=99)), 3)

    def test_recommendations_are_cached(self):
        car = Car.objects.get(pk=self.reference_id)

        first = recommend_similar_cars(car, limit=2)
        second = recommend_similar_cars(car, limit=2)

        self.assertEqual([c.pk for c in first], [c.pk for c in second])
        cache_key = f'similar_cars:{car.pk}:2'
        self.assertIsNotNone(cache.get(cache_key))

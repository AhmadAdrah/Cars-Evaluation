from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.cars.models import Car, FavoriteCar
from apps.cars.services.price_prediction_service import predict_price_from_request

User = get_user_model()

CARS_LIST_URL = '/api/cars/'
CREATE_URL = '/api/cars/create/'
FAVORITES_URL = '/api/cars/favorites/'
TOGGLE_FAV_URL = '/api/cars/{pk}/favorite/'
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


class FavoritesTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='fav-user@example.com', password='StrongPass123!')
        self.seller = User.objects.create_user(email='fav-seller@example.com', password='StrongPass123!')
        self.admin = User.objects.create_superuser(email='fav-admin@example.com', password='Admin123!')

        self.client.force_authenticate(self.seller)
        created = self.client.post(CREATE_URL, car_data(), format="json")
        self.car_id = created.data['car']['id']
        self.client.force_authenticate(self.admin)
        self.client.post(f'/api/cars/{self.car_id}/approve/')
        self.client.force_authenticate(self.user)

    def test_toggle_adds_and_removes_favorite(self):
        add = self.client.post(TOGGLE_FAV_URL.format(pk=self.car_id))
        self.assertEqual(add.status_code, 201)
        self.assertTrue(add.data['is_favorited'])
        self.assertTrue(FavoriteCar.objects.filter(user=self.user, car_id=self.car_id).exists())

        remove = self.client.post(TOGGLE_FAV_URL.format(pk=self.car_id))
        self.assertEqual(remove.status_code, 200)
        self.assertFalse(remove.data['is_favorited'])
        self.assertFalse(FavoriteCar.objects.filter(user=self.user, car_id=self.car_id).exists())

    def test_toggle_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.post(TOGGLE_FAV_URL.format(pk=self.car_id))
        self.assertEqual(response.status_code, 401)

    def test_favorites_list_shows_only_own_favorites_paginated(self):
        other_user = User.objects.create_user(email='other-fav@example.com', password='StrongPass123!')
        FavoriteCar.objects.create(user=other_user, car=Car.objects.get(pk=self.car_id))

        self.client.post(TOGGLE_FAV_URL.format(pk=self.car_id))
        response = self.client.get(FAVORITES_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.car_id)
        self.assertTrue(response.data['results'][0]['is_favorited'])

    def test_detail_includes_is_favorited_for_authenticated_user(self):
        detail_plain = self.client.get(DETAIL_URL.format(pk=self.car_id))
        self.assertFalse(detail_plain.data['car']['is_favorited'])

        self.client.post(TOGGLE_FAV_URL.format(pk=self.car_id))
        detail_faved = self.client.get(DETAIL_URL.format(pk=self.car_id))
        self.assertTrue(detail_faved.data['car']['is_favorited'])

    def test_cannot_favorite_non_available_car(self):
        car = Car.objects.get(pk=self.car_id)
        car.status = Car.Status.SOLD
        car.save(update_fields=['status'])

        response = self.client.post(TOGGLE_FAV_URL.format(pk=self.car_id))
        self.assertEqual(response.status_code, 404)

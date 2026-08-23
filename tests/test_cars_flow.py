import io
import struct
import zlib

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APITestCase

from apps.cars.models import Car, CarImage
from apps.cars.services.price_prediction_service import predict_price_from_request

User = get_user_model()

CARS_LIST_URL = '/api/cars/'
CREATE_URL = '/api/cars/create/'
MY_CARS_URL = '/api/cars/my-cars/'
APPROVE_URL = '/api/cars/{pk}/approve/'
REJECT_URL = '/api/cars/{pk}/reject/'
MARK_SOLD_URL = '/api/cars/admin/cars/{pk}/mark-sold/'
ADMIN_PENDING_URL = '/api/cars/admin/pending/'
ADMIN_ALL_URL = '/api/cars/admin/all/'

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
    'price_usd': 20000,
}


def build_png_bytes(width=1, height=1):
    """Build a minimal valid PNG so Pillow validation passes."""
    def chunk(chunk_type, data):
        return (
            struct.pack('>I', len(data))
            + chunk_type
            + data
            + struct.pack('>I', zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    raw = b''.join(b'\x00' + b'\xff\x00\x00' * width for _ in range(height))
    return (
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', header)
        + chunk(b'IDAT', zlib.compress(raw))
        + chunk(b'IEND', b'')
    )


def make_test_image(name='photo.png', width=1, height=1):
    return SimpleUploadedFile(
        name, build_png_bytes(width, height), content_type='image/png',
    )


class CarListingFlowTests(APITestCase):
    """End-to-end: seller creates listing -> admin moderates -> public visibility."""

    def setUp(self):
        self.seller = User.objects.create_user(email='seller@example.com', password='StrongPass123!')
        self.admin = User.objects.create_superuser(email='admin2@example.com', password='Admin123!')
        self.client.force_authenticate(self.seller)

    def _predicted_range_for(self, data):
        prediction = predict_price_from_request(data)
        return (
            float(prediction['predicted_price_usd']),
            float(prediction['price_range']['min_price_usd']),
            float(prediction['price_range']['max_price_usd']),
        )

    def test_create_listing_within_band_is_pending_with_estimated_price(self):
        predicted, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        payload = {**CAR_BASE_DATA, 'price_usd': round((min_price + max_price) / 2, 2)}

        response = self.client.post(CREATE_URL, payload, format='json')

        self.assertEqual(response.status_code, 201)
        car = Car.objects.get(pk=response.data['car']['id'])
        self.assertEqual(car.status, Car.Status.PENDING)
        self.assertIsNotNone(car.estimated_price_usd)

    def test_create_listing_outside_band_returns_422_with_range(self):
        predicted, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        payload = {**CAR_BASE_DATA, 'price_usd': round(max_price * 3 + 100000, 2)}

        response = self.client.post(CREATE_URL, payload, format='json')

        self.assertEqual(response.status_code, 422)
        self.assertIn('price_range', response.data)
        self.assertIn('submitted_price_usd', response.data)
        self.assertEqual(Car.objects.count(), 0)

    def test_create_listing_with_images_in_same_request(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        payload = {
            **CAR_BASE_DATA,
            'price_usd': round((min_price + max_price) / 2, 2),
            'images': [make_test_image('front.png'), make_test_image('back.png')],
        }

        response = self.client.post(CREATE_URL, payload, format='multipart')

        self.assertEqual(response.status_code, 201)
        car = Car.objects.get(pk=response.data['car']['id'])
        images = list(car.images.order_by('pk'))
        self.assertEqual(len(images), 2)
        self.assertTrue(images[0].is_primary)
        self.assertFalse(images[1].is_primary)
        self.assertGreater(len(images[0].image_data), 0)

        first_image_url = response.data['car']['images'][0]['image']
        self.assertEqual(first_image_url, f'/api/cars/images/{images[0].pk}/')
        image_response = self.client.get(first_image_url)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response['Content-Type'], 'image/jpeg')
        self.assertEqual(image_response.content, bytes(images[0].image_data))

    def test_my_cars_list_returns_database_image_urls(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL,
            {
                **CAR_BASE_DATA,
                'price_usd': round((min_price + max_price) / 2, 2),
                'images': [make_test_image('front.png')],
            },
            format='multipart',
        )
        car_id = created.data['car']['id']

        listing = self.client.get(MY_CARS_URL)

        self.assertEqual(listing.status_code, 200)
        item = next(c for c in listing.data['results'] if c['id'] == car_id)
        image_url = item['images'][0]['image']
        self.assertEqual(image_url, f"/api/cars/images/{item['images'][0]['id']}/")

    def test_create_listing_sanitizes_description(self):
        predicted, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        payload = {
            **CAR_BASE_DATA,
            'description': '<script>alert(1)</script>Clean car   with <b>low</b> mileage. Contact www.spam.com',
            'price_usd': round((min_price + max_price) / 2, 2),
        }

        response = self.client.post(CREATE_URL, payload, format='json')
        self.assertEqual(response.status_code, 201)

        car = Car.objects.get(pk=response.data['car']['id'])
        self.assertNotIn('<script>', car.description)
        self.assertNotIn('<b>', car.description)
        self.assertIn('Clean car', car.description)
        self.assertIn('[link removed]', car.description)

    def test_admin_can_approve_pending_listing_making_it_public(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL, {**CAR_BASE_DATA, 'price_usd': round((min_price + max_price) / 2, 2)}, format='json',
        )
        car_id = created.data['car']['id']

        self.client.force_authenticate(self.admin)
        approve = self.client.post(APPROVE_URL.format(pk=car_id))
        self.assertEqual(approve.status_code, 200)

        public_list = self.client.get(CARS_LIST_URL)
        self.assertEqual(public_list.status_code, 200)
        ids = [item['id'] for item in public_list.data['results']]
        self.assertIn(car_id, ids)

    def test_reject_saves_reason_and_seller_sees_it(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL, {**CAR_BASE_DATA, 'price_usd': round((min_price + max_price) / 2, 2)}, format='json',
        )
        car_id = created.data['car']['id']

        self.client.force_authenticate(self.admin)
        reject = self.client.post(
            REJECT_URL.format(pk=car_id), {'reason': 'Images are unclear.'}, format='json',
        )
        self.assertEqual(reject.status_code, 200)

        car = Car.objects.get(pk=car_id)
        self.assertEqual(car.status, Car.Status.REJECTED)
        self.assertEqual(car.rejection_reason, 'Images are unclear.')

        self.client.force_authenticate(self.seller)
        my_cars = self.client.get(MY_CARS_URL, {'status': 'REJECTED'})
        rejected = [c for c in my_cars.data['results'] if c['id'] == car_id]
        self.assertTrue(rejected)
        self.assertEqual(rejected[0]['rejection_reason'], 'Images are unclear.')

    def test_invalid_status_transitions_return_400(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL, {**CAR_BASE_DATA, 'price_usd': round((min_price + max_price) / 2, 2)}, format='json',
        )
        car_id = created.data['car']['id']
        self.client.force_authenticate(self.admin)

        sold_first = self.client.post(MARK_SOLD_URL.format(pk=car_id))
        self.assertEqual(sold_first.status_code, 400)

        self.client.post(REJECT_URL.format(pk=car_id))
        re_approve = self.client.post(APPROVE_URL.format(pk=car_id))
        self.assertEqual(re_approve.status_code, 400)

    def test_seller_edit_resets_status_to_pending(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL, {**CAR_BASE_DATA, 'price_usd': round((min_price + max_price) / 2, 2)}, format='json',
        )
        car_id = created.data['car']['id']
        self.client.force_authenticate(self.admin)
        self.client.post(APPROVE_URL.format(pk=car_id))

        self.client.force_authenticate(self.seller)
        edit = self.client.patch(
            f'{MY_CARS_URL}{car_id}/', {'mileage_km': 65000}, format='json',
        )
        self.assertEqual(edit.status_code, 200)
        car = Car.objects.get(pk=car_id)
        self.assertEqual(car.status, Car.Status.PENDING)

    def test_update_listing_with_images_in_same_request(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL,
            {
                **CAR_BASE_DATA,
                'price_usd': round((min_price + max_price) / 2, 2),
                'images': [make_test_image('front.png')],
            },
            format='multipart',
        )
        car_id = created.data['car']['id']

        edit = self.client.patch(
            f'{MY_CARS_URL}{car_id}/',
            {
                'mileage_km': 61000,
                'images': [make_test_image('side.png'), make_test_image('rear.png')],
            },
            format='multipart',
        )

        self.assertEqual(edit.status_code, 200)
        car = Car.objects.get(pk=car_id)
        self.assertEqual(car.mileage_km, 61000)
        images = list(car.images.order_by('pk'))
        self.assertEqual(len(images), 3)
        self.assertTrue(images[0].is_primary)
        self.assertFalse(images[1].is_primary)
        self.assertFalse(images[2].is_primary)

    def test_image_only_update_attaches_images_and_resets_status(self):
        _, min_price, max_price = self._predicted_range_for(CAR_BASE_DATA)
        created = self.client.post(
            CREATE_URL, {**CAR_BASE_DATA, 'price_usd': round((min_price + max_price) / 2, 2)}, format='json',
        )
        car_id = created.data['car']['id']
        self.client.force_authenticate(self.admin)
        self.client.post(APPROVE_URL.format(pk=car_id))

        self.client.force_authenticate(self.seller)
        edit = self.client.patch(
            f'{MY_CARS_URL}{car_id}/',
            {'images': [make_test_image('interior.png')]},
            format='multipart',
        )

        self.assertEqual(edit.status_code, 200)
        car = Car.objects.get(pk=car_id)
        self.assertEqual(car.status, Car.Status.PENDING)
        images = list(car.images.order_by('pk'))
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0].is_primary)


class CarListFilteringTests(APITestCase):
    def setUp(self):
        self.seller = User.objects.create_user(email='list-seller@example.com', password='StrongPass123!')
        self.admin = User.objects.create_superuser(email='list-admin@example.com', password='Admin123!')
        self.client.force_authenticate(self.seller)

    def _create_approved_car(self, **overrides):
        data = self._in_band_data(**overrides)
        created = self.client.post(CREATE_URL, data, format='json')
        car_id = created.data['car']['id']
        self.client.force_authenticate(self.admin)
        approve = self.client.post(APPROVE_URL.format(pk=car_id))
        assert approve.status_code == 200, approve.data
        return Car.objects.get(pk=car_id)

    @staticmethod
    def _in_band_data(**overrides):
        from apps.cars.services.price_prediction_service import predict_price_from_request

        data = {**CAR_BASE_DATA, **overrides}
        prediction = predict_price_from_request(data)
        low = float(prediction['price_range']['min_price_usd'])
        high = float(prediction['price_range']['max_price_usd'])
        data['price_usd'] = round((low + high) / 2, 2)
        return data

    def test_public_list_pagination_envelope(self):
        for i in range(3):
            self._create_approved_car(mileage_km=60000 + i)

        response = self.client.get(CARS_LIST_URL, {'page_size': 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['pages'], 2)
        self.assertEqual(response.data['page'], 1)

        page2 = self.client.get(CARS_LIST_URL, {'page_size': 2, 'page': 2})
        self.assertEqual(len(page2.data['results']), 1)

    def test_public_list_hides_non_available(self):
        self._create_approved_car()

        pending_payload = {**CAR_BASE_DATA, 'brand': 'Honda', 'base_model': 'Civic'}
        self.client.post(CREATE_URL, pending_payload, format='json')

        response = self.client.get(CARS_LIST_URL)
        brands = {item['brand'] for item in response.data['results']}
        self.assertNotIn('Honda', brands)

    def test_brand_and_price_filters(self):
        cheap = self._create_approved_car(brand='Ford', base_model='F-150')
        expensive = self._create_approved_car(brand='BMW', base_model='X5')

        response = self.client.get(CARS_LIST_URL, {'brand': 'ford'})
        ids = {item['id'] for item in response.data['results']}
        self.assertIn(cheap.id, ids)
        self.assertNotIn(expensive.id, ids)

    def test_my_cars_requires_auth_and_scopes_to_owner(self):
        other = User.objects.create_user(email='other@example.com', password='StrongPass123!')
        car = self._create_approved_car()
        Car.objects.create(seller=other, status=Car.Status.AVAILABLE, **{
            k: v for k, v in CAR_BASE_DATA.items() if k != 'price_usd'
        } | {'price_usd': 15000})

        self.client.force_authenticate(self.seller)
        response = self.client.get(MY_CARS_URL)

        ids = {item['id'] for item in response.data['results']}
        self.assertIn(car.id, ids)
        self.assertEqual(len(ids), 1)


class CarImageValidationTests(APITestCase):
    """Uploaded files must be real images within limits before anything is stored."""

    def setUp(self):
        self.seller = User.objects.create_user(email='img-seller@example.com', password='StrongPass123!')
        self.client.force_authenticate(self.seller)

    def _in_band_payload(self, **overrides):
        prediction = predict_price_from_request(CAR_BASE_DATA)
        low = float(prediction['price_range']['min_price_usd'])
        high = float(prediction['price_range']['max_price_usd'])
        return {**CAR_BASE_DATA, 'price_usd': round((low + high) / 2, 2), **overrides}

    def test_create_listing_rejects_non_image_file(self):
        fake = SimpleUploadedFile('not-an-image.png', b'definitely not a png', content_type='image/png')
        payload = self._in_band_payload(images=[fake])

        response = self.client.post(CREATE_URL, payload, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('valid image', response.data['detail'])
        self.assertEqual(Car.objects.count(), 0)

    def test_create_listing_rejects_corrupt_image_bytes(self):
        truncated = SimpleUploadedFile('truncated.png', build_png_bytes()[:20], content_type='image/png')
        payload = self._in_band_payload(images=[truncated])

        response = self.client.post(CREATE_URL, payload, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Car.objects.count(), 0)

    def test_create_listing_enforces_max_images_per_request(self):
        payload = self._in_band_payload(
            images=[make_test_image(f'img{i}.png') for i in range(11)],
        )

        response = self.client.post(CREATE_URL, payload, format='multipart')

        self.assertEqual(response.status_code, 400)
        self.assertIn('maximum', response.data['detail'])
        self.assertEqual(Car.objects.count(), 0)

    def test_update_listing_rejects_invalid_image_files(self):
        created = self.client.post(CREATE_URL, self._in_band_payload(), format='json')
        car_id = created.data['car']['id']
        fake = SimpleUploadedFile('fake.png', b'nope', content_type='image/png')

        response = self.client.patch(
            f'{MY_CARS_URL}{car_id}/', {'images': [fake]}, format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        car = Car.objects.get(pk=car_id)
        self.assertEqual(car.images.count(), 0)


class CarImageStorageTests(APITestCase):
    """Prove uploaded images land in the database as compressed JPEG binaries."""

    def setUp(self):
        self.seller = User.objects.create_user(email='storage-seller@example.com', password='StrongPass123!')
        self.client.force_authenticate(self.seller)

    def _create_with_image(self, width=1, height=1, filename='front.png'):
        prediction = predict_price_from_request(CAR_BASE_DATA)
        low = float(prediction['price_range']['min_price_usd'])
        high = float(prediction['price_range']['max_price_usd'])
        payload = {
            **CAR_BASE_DATA,
            'price_usd': round((low + high) / 2, 2),
            'images': [make_test_image(filename, width=width, height=height)],
        }
        return self.client.post(CREATE_URL, payload, format='multipart')

    def test_uploaded_png_is_served_from_stored_jpeg_binary(self):
        response = self._create_with_image()

        self.assertEqual(response.status_code, 201)
        car_image = CarImage.objects.get(car_id=response.data['car']['id'])
        self.assertEqual(car_image.content_type, 'image/jpeg')
        self.assertTrue(car_image.image_data.startswith(b'\xff\xd8'))

        image_url = response.data['car']['images'][0]['image']
        image_response = self.client.get(image_url)
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response['Content-Type'], 'image/jpeg')
        self.assertEqual(image_response.content, bytes(car_image.image_data))
        with Image.open(io.BytesIO(image_response.content)) as img:
            self.assertEqual(img.format, 'JPEG')

    def test_large_uploads_are_downscaled_before_storage(self):
        response = self._create_with_image(width=2000, height=1500, filename='big.png')

        self.assertEqual(response.status_code, 201)
        car_image = CarImage.objects.get(car_id=response.data['car']['id'])
        with Image.open(io.BytesIO(car_image.image_data)) as img:
            self.assertLessEqual(max(img.size), 1280)

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

REGISTER_URL = '/api/accounts/register/'
VERIFY_URL = '/api/accounts/verify-otp/'
CLIENT_LOGIN_URL = '/api/accounts/login/client/'
ADMIN_LOGIN_URL = '/api/accounts/login/admin/'
FORGOT_URL = '/api/accounts/password/forgot/'
VERIFY_RESET_URL = '/api/accounts/password/verify-otp/'
RESET_URL = '/api/accounts/password/reset/'
PROFILE_URL = '/api/accounts/profile/'
CHANGE_PASSWORD_URL = '/api/accounts/profile/change-password/'


def otp_code_from_mail():
    body = mail.outbox[-1].body
    for token in body.replace('.', ' ').split():
        if token.isdigit() and len(token) == 6:
            return token
    return None


class AccountsFlowTests(TestCase):
    def test_user_can_be_created_with_email_and_password(self):
        user = User.objects.create_user(email='test@example.com', password='StrongPass123!')

        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('StrongPass123!'))

    def test_user_has_default_role_and_car_permissions(self):
        user = User.objects.create_user(email='buyer@example.com', password='StrongPass123!')

        self.assertEqual(user.role, User.Role.USER)
        self.assertTrue(user.can_sell_cars)
        self.assertTrue(user.can_rate_cars)
        self.assertTrue(user.can_buy_cars)

    def test_superuser_can_be_created(self):
        user = User.objects.create_superuser(email='admin@example.com', password='Admin123!')

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.can_sell_cars)
        self.assertTrue(user.can_rate_cars)
        self.assertTrue(user.can_buy_cars)


class AccountsApiFlowTests(APITestCase):
    def _register_payload(self, email='newuser@example.com'):
        return {
            'name': 'New User',
            'email': email,
            'phone_number': '1234567890',
            'password': 'StrongPass123!',
        }

    def test_register_sends_otp_and_creates_inactive_user(self):
        response = self.client.post(REGISTER_URL, self._register_payload())

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_register_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(email='taken@example.com', password='StrongPass123!')

        payload = self._register_payload(email='TAKEN@example.com')
        response = self.client.post(REGISTER_URL, payload)

        self.assertEqual(response.status_code, 400)

    def test_verify_otp_activates_account_and_returns_tokens(self):
        self.client.post(REGISTER_URL, self._register_payload())
        code = otp_code_from_mail()

        response = self.client.post(VERIFY_URL, {
            'email': 'newuser@example.com', 'code': code, 'purpose': 'REGISTER_VERIFY',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('tokens', response.data)
        self.assertTrue(User.objects.get(email='newuser@example.com').is_active)

    def test_client_login_rejects_admin_role(self):
        User.objects.create_superuser(email='boss@example.com', password='Admin123!')
        response = self.client.post(CLIENT_LOGIN_URL, {
            'email': 'boss@example.com', 'password': 'Admin123!',
        })
        self.assertEqual(response.status_code, 403)

    def test_admin_login_rejects_regular_user(self):
        User.objects.create_user(email='plain@example.com', password='StrongPass123!')
        response = self.client.post(ADMIN_LOGIN_URL, {
            'email': 'plain@example.com', 'password': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 403)

    def test_password_reset_flow(self):
        User.objects.create_superuser(email='resetme@example.com', password='OldPass123!')

        self.client.post(FORGOT_URL, {'email': 'resetme@example.com'})
        code = otp_code_from_mail()
        self.assertIsNotNone(code)

        verify_response = self.client.post(VERIFY_RESET_URL, {
            'email': 'resetme@example.com', 'code': code,
        })
        self.assertEqual(verify_response.status_code, 200)

        reset_response = self.client.post(RESET_URL, {
            'email': 'resetme@example.com', 'code': code, 'new_password': 'NewPass456!',
        })
        self.assertEqual(reset_response.status_code, 200)

        login_response = self.client.post(ADMIN_LOGIN_URL, {
            'email': 'resetme@example.com', 'password': 'NewPass456!',
        })
        self.assertEqual(login_response.status_code, 200)


class ProfileApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='profile@example.com', password='StrongPass123!', name='Original Name',
        )

    def _authenticate(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_profile_requires_authentication(self):
        response = self.client.get(PROFILE_URL)
        self.assertEqual(response.status_code, 401)

    def test_get_profile(self):
        self._authenticate()
        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'profile@example.com')
        self.assertEqual(response.data['name'], 'Original Name')

    def test_update_profile_name_and_phone(self):
        self._authenticate()
        response = self.client.patch(PROFILE_URL, {'name': 'Updated Name', 'phone_number': '0987654321'})

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Updated Name')
        self.assertEqual(self.user.phone_number, '0987654321')

    def test_change_password_with_wrong_current_password(self):
        self._authenticate()
        response = self.client.post(CHANGE_PASSWORD_URL, {
            'current_password': 'WrongPass!', 'new_password': 'NewPass456!',
        })
        self.assertEqual(response.status_code, 400)

    def test_change_password_success(self):
        self._authenticate()
        response = self.client.post(CHANGE_PASSWORD_URL, {
            'current_password': 'StrongPass123!', 'new_password': 'NewPass456!',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))

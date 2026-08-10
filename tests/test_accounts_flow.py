from django.contrib.auth import get_user_model
from django.test import TestCase


class AccountsFlowTests(TestCase):
    def test_user_can_be_created_with_email_and_password(self):
        User = get_user_model()
        user = User.objects.create_user(email='test@example.com', password='StrongPass123!')

        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('StrongPass123!'))

    def test_user_has_default_role_and_car_permissions(self):
        User = get_user_model()
        user = User.objects.create_user(email='buyer@example.com', password='StrongPass123!')

        self.assertEqual(user.role, User.Role.USER)
        self.assertTrue(user.can_sell_cars)
        self.assertTrue(user.can_rate_cars)
        self.assertTrue(user.can_buy_cars)

    def test_superuser_can_be_created(self):
        User = get_user_model()
        user = User.objects.create_superuser(email='admin@example.com', password='Admin123!')

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.can_sell_cars)
        self.assertTrue(user.can_rate_cars)
        self.assertTrue(user.can_buy_cars)

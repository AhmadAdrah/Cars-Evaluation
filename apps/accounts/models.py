from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        USER = 'USER', 'User'
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    can_sell_cars = models.BooleanField(default=True)
    can_rate_cars = models.BooleanField(default=True)
    can_buy_cars = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.can_sell_cars = True
            self.can_rate_cars = True
            self.can_buy_cars = True
        elif self.role == self.Role.USER:
            self.can_sell_cars = True
            self.can_rate_cars = True
            self.can_buy_cars = True
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email


class OTP(models.Model):
    REGISTER_VERIFY = 'REGISTER_VERIFY'
    PASSWORD_RESET = 'PASSWORD_RESET'
    PURPOSE_CHOICES = [
        (REGISTER_VERIFY, 'Register Verify'),
        (PASSWORD_RESET, 'Password Reset'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(blank=True, default='')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.email or self.user.email} - {self.code}'

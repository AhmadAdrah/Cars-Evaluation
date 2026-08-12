from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from ..models import User
from ..selectors.user_selector import get_user_by_email
from .otp_service import generate_and_send_email_otp, verify_otp_code


@transaction.atomic
def register_user(*, email: str, password: str, name: str, phone_number: str | None = None) -> User:
    user = get_user_by_email(email)
    if user is not None:
        raise ValueError('User with this email already exists.')

    return User.objects.create_user(email=email, password=password, name=name, phone_number=phone_number)


def get_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@transaction.atomic
def activate_user_account(*, email: str) -> User:
    user = get_user_by_email(email)
    if user is None:
        raise ValueError('User not found.')

    user.is_active = True
    user.save(update_fields=['is_active'])
    return user


def authenticate_user(*, email: str, password: str):
    user = authenticate(request=None, username=email, password=password)
    if user is None:
        raise AuthenticationFailed('Invalid credentials.')
    return user


def authenticate_admin(*, email: str, password: str):
    user = authenticate_user(email=email, password=password)
    if user.role != User.Role.ADMIN:
        raise PermissionDenied('Admin access required.')
    return user


def authenticate_client(*, email: str, password: str):
    user = authenticate_user(email=email, password=password)
    if user.role != User.Role.USER:
        raise PermissionDenied('Client access required.')
    return user


@transaction.atomic
def send_password_reset_otp(*, email: str) -> None:
    generate_and_send_email_otp(email=email, purpose='PASSWORD_RESET')


@transaction.atomic
def reset_user_password(*, email: str, code: str, new_password: str) -> User:
    verify_otp_code(email=email, code=code, purpose='PASSWORD_RESET')

    user = get_user_by_email(email)
    if user is None:
        raise ValueError('User not found.')

    user.set_password(new_password)
    user.save(update_fields=['password'])
    return user

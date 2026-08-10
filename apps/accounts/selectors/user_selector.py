from django.db.models import Q

from ..models import OTP, User


def get_user_by_email(email: str) -> User | None:
    return User.objects.filter(email__iexact=email).first()


def user_exists(email: str) -> bool:
    return User.objects.filter(email__iexact=email).exists()


def get_active_otp(email: str, purpose: str) -> OTP | None:
    return (
        OTP.objects.filter(
            Q(email__iexact=email) | Q(user__email__iexact=email),
            purpose=purpose,
            is_used=False,
        )
        .order_by('-created_at')
        .first()
    )

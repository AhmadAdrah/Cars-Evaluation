import random
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from ..models import OTP
from ..selectors.user_selector import get_active_otp


@transaction.atomic
def generate_and_send_email_otp(*, email: str, purpose: str) -> OTP:
    code = f'{random.randint(100000, 999999)}'
    otp = OTP.objects.create(
        email=email,
        code=code,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=10),
        is_used=False,
    )
    send_mail(
        subject='Your verification code',
        message=f'Your OTP code is {code}. It expires in 10 minutes.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    return otp


@transaction.atomic
def check_otp_code(*, email: str, code: str, purpose: str) -> OTP:
    otp = get_active_otp(email=email, purpose=purpose)
    if otp is None:
        raise ValueError('No active OTP found.')
    if otp.code != code:
        raise ValueError('Invalid OTP code.')
    if otp.expires_at < timezone.now():
        raise ValueError('OTP has expired.')
    return otp


@transaction.atomic
def verify_otp_code(*, email: str, code: str, purpose: str) -> OTP:
    otp = check_otp_code(email=email, code=code, purpose=purpose)

    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return otp

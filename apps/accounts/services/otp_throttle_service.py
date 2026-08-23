from django.core.cache import cache

OTP_SEND_LIMIT_PER_HOUR = 5
OTP_VERIFY_ATTEMPTS_PER_HOUR = 10
THROTTLE_WINDOW_SECONDS = 3600


def _key(kind: str, email: str) -> str:
    return f'otp-throttle:{kind}:{email.lower()}'


class OTPThrottled(ValueError):
    """Raised when an email exceeds the allowed OTP send/verify rate."""


def check_send_allowed(email: str) -> None:
    key = _key('send', email)
    count = cache.get(key, 0)
    if count >= OTP_SEND_LIMIT_PER_HOUR:
        raise OTPThrottled('Too many OTP requests. Please try again later.')
    cache.set(key, count + 1, THROTTLE_WINDOW_SECONDS)


def check_verify_allowed(email: str) -> None:
    key = _key('verify', email)
    attempts = cache.get(key, 0)
    if attempts >= OTP_VERIFY_ATTEMPTS_PER_HOUR:
        raise OTPThrottled('Too many verification attempts. Please request a new code later.')
    cache.set(key, attempts + 1, THROTTLE_WINDOW_SECONDS)

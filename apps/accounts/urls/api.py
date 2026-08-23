from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from ..api.views import (
    AdminLoginAPIView,
    ChangePasswordAPIView,
    ClientLoginAPIView,
    ForgotPasswordAPIView,
    LoginAPIView,
    ProfileAPIView,
    RegisterAPIView,
    ResetPasswordAPIView,
    VerifyOTPAPIView,
    VerifyPasswordResetOTPAPIView,
)

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='accounts-register'),
    path('verify-otp/', VerifyOTPAPIView.as_view(), name='accounts-verify-otp'),
    path('login/', LoginAPIView.as_view(), name='accounts-login'),
    path('login/admin/', AdminLoginAPIView.as_view(), name='accounts-admin-login'),
    path('login/client/', ClientLoginAPIView.as_view(), name='accounts-client-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='accounts-token-refresh'),
    path('password/forgot/', ForgotPasswordAPIView.as_view(), name='accounts-forgot-password'),
    path('password/verify-otp/', VerifyPasswordResetOTPAPIView.as_view(), name='accounts-verify-password-otp'),
    path('password/reset/', ResetPasswordAPIView.as_view(), name='accounts-reset-password'),
    path('profile/', ProfileAPIView.as_view(), name='accounts-profile'),
    path('profile/change-password/', ChangePasswordAPIView.as_view(), name='accounts-change-password'),
]
